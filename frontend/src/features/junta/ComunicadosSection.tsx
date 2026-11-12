import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Send } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import { Field, Input, Textarea } from "@/components/ui/Field";
import {
  atenderAlertaNotificacion,
  listarAlertasNotificacion,
  reenviarNotificacion,
  type AlertaNotificacion,
  type NotificacionLog,
  type TipoAlertaNotificacion,
} from "@/lib/api";
import { formatDate } from "@/lib/format";

interface ComunicadosSectionProps {
  loading: boolean;
  notificaciones: NotificacionLog[];
  condominioId: string | null;
  isAuditor: boolean;
  titulo: string;
  mensaje: string;
  onTituloChange: (value: string) => void;
  onMensajeChange: (value: string) => void;
  onSubmit: (event: FormEvent) => void;
  onActualizada: () => void;
}

const ESTADOS_NOTIFICACION: Record<
  NotificacionLog["estado"],
  { label: string; tone: "success" | "warning" | "danger" | "info" }
> = {
  ENTREGADO: { label: "Entregado", tone: "success" },
  ENVIADO: { label: "Aceptado, entrega sin confirmar", tone: "info" },
  REINTENTANDO: { label: "Reintentando", tone: "warning" },
  FALLIDO_PERMANENTE: { label: "Fallido", tone: "danger" },
  EN_COLA: { label: "En cola", tone: "info" },
};

const TIPOS_ALERTA: Record<TipoAlertaNotificacion, string> = {
  ERROR_DEFINITIVO: "Error definitivo de entrega",
  INTENTOS_AGOTADOS: "Intentos agotados",
  ACEPTACION_INCIERTA: "Aceptación sin confirmar",
  DESTINATARIO_INVALIDO: "Destinatario inválido",
  PROVEEDOR_NO_CONFIGURADO: "Proveedor no configurado",
};

function AlertasEntrega({
  condominioId,
  isAuditor,
  version,
}: {
  condominioId: string | null;
  isAuditor: boolean;
  version: number;
}) {
  const [alertas, setAlertas] = useState<AlertaNotificacion[]>([]);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [atendiendo, setAtendiendo] = useState<string | null>(null);

  const cargar = useCallback(async () => {
    if (!condominioId) {
      setAlertas([]);
      setCargando(false);
      return;
    }
    setCargando(true);
    setError(null);
    try {
      setAlertas(await listarAlertasNotificacion(condominioId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "No pudimos cargar las alertas de entrega.");
    } finally {
      setCargando(false);
    }
  }, [condominioId]);

  useEffect(() => {
    void cargar();
  }, [cargar, version]);

  async function atender(id: string) {
    setAtendiendo(id);
    setErrorAccion(null);
    try {
      await atenderAlertaNotificacion(id);
      await cargar();
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : "No pudimos marcar la alerta como atendida.");
    } finally {
      setAtendiendo(null);
    }
  }

  return (
    <Card className="xl:col-span-2">
      <CardHeader
        title="Alertas de entrega"
        description="Avisos que no pudieron entregarse y requieren revisar los datos de contacto."
      />
      <CardBody>
        {errorAccion && <Alert tone="danger">{errorAccion}</Alert>}
        {cargando ? (
          <SkeletonList rows={2} label="Cargando alertas de entrega" />
        ) : error ? (
          <div className="space-y-3">
            <Alert tone="danger">{error}</Alert>
            <Button variant="secondary" size="sm" onClick={() => void cargar()}>
              Reintentar
            </Button>
          </div>
        ) : alertas.length === 0 ? (
          <EmptyState
            title="Sin alertas abiertas"
            description="Las entregas fallidas que requieran atención aparecerán aquí."
          />
        ) : (
          <ul className="divide-y divide-line">
            {alertas.map((alerta) => (
              <li
                key={alerta.id}
                className="flex flex-wrap items-center justify-between gap-3 py-3"
              >
                <div>
                  <p className="font-medium">
                    Dpto. {alerta.departamento_numero} · {TIPOS_ALERTA[alerta.tipo] ?? alerta.tipo}
                  </p>
                  <p className="mt-1 text-sm">{alerta.mensaje}</p>
                  <p className="mt-1 text-xs text-muted">{formatDate(alerta.creada_en)}</p>
                </div>
                {!isAuditor && (
                  <Button
                    variant="secondary"
                    size="sm"
                    loading={atendiendo === alerta.id}
                    disabled={atendiendo !== null}
                    onClick={() => void atender(alerta.id)}
                  >
                    Marcar como atendida
                  </Button>
                )}
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

export function ComunicadosSection({
  loading,
  notificaciones,
  condominioId,
  isAuditor,
  titulo,
  mensaje,
  onTituloChange,
  onMensajeChange,
  onSubmit,
  onActualizada,
}: ComunicadosSectionProps) {
  const [seleccion, setSeleccion] = useState<string | null>(null);
  const [contacto, setContacto] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [versionAlertas, setVersionAlertas] = useState(0);

  async function reencolar(event: FormEvent) {
    event.preventDefault();
    if (!seleccion) return;
    setBusy(true);
    setError(null);
    try {
      await reenviarNotificacion(seleccion, contacto.trim());
      setSeleccion(null);
      setVersionAlertas((v) => v + 1);
      onActualizada();
    } catch (e) {
      setError(e instanceof Error ? e.message : "No pudimos reencolar el aviso.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
      <Card>
        <CardHeader
          title="Comunicado a la comunidad"
          description="Redacta un aviso para los residentes del condominio."
        />
        <CardBody>
          {isAuditor ? (
            <div className="rounded-lg border border-audit-200 bg-audit-50 p-3">
              <Badge tone="audit">Solo lectura</Badge>
              <p className="mt-2 text-sm text-audit-800">
                El envío de comunicados no está disponible para auditoría.
              </p>
            </div>
          ) : (
            <form onSubmit={onSubmit} className="space-y-4">
              <Field label="Título" required>
                <Input
                  value={titulo}
                  onChange={(event) => onTituloChange(event.target.value)}
                  autoComplete="off"
                />
              </Field>
              <Field label="Mensaje" required>
                <Textarea
                  value={mensaje}
                  onChange={(event) => onMensajeChange(event.target.value)}
                  rows={5}
                />
              </Field>
              <Button
                type="submit"
                icon={<Send className="h-4 w-4" aria-hidden="true" />}
              >
                Enviar comunicado
              </Button>
            </form>
          )}
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Historial de envíos" />
        <CardBody>
          {error && <Alert tone="danger">{error}</Alert>}
          {loading ? (
            <SkeletonList rows={3} label="Cargando historial de comunicados" />
          ) : notificaciones.length === 0 ? (
            <EmptyState
              title="Sin envíos registrados"
              description="El historial aparecerá aquí después de enviar un comunicado."
            />
          ) : (
            <ul className="divide-y divide-line">
              {notificaciones.map((notificacion) => {
                const estado = ESTADOS_NOTIFICACION[notificacion.estado];
                return (
                  <li
                    key={notificacion.id}
                    className="flex flex-wrap items-center justify-between gap-3 py-3"
                  >
                    <div>
                      <p className="font-medium">
                        {notificacion.asunto || notificacion.tipo_evento}
                      </p>
                      <p className="mt-1 text-xs text-muted">
                        {notificacion.destinatario} · {notificacion.canal} ·{" "}
                        {formatDate(notificacion.fecha_creacion)}
                      </p>
                      <p className="text-xs text-muted">
                        Ciclo {notificacion.ciclo} · Intentos: {notificacion.intentos}
                        {notificacion.transporte === "SIMULADO" ? " · Transporte simulado" : ""}
                      </p>
                      {notificacion.proximo_reintento && <p className="text-xs text-muted">
                        Próximo intento: {formatDate(notificacion.proximo_reintento)}
                      </p>}
                      {notificacion.error_mensaje && <p className="text-sm text-danger-700">{notificacion.error_mensaje}</p>}
                      {!isAuditor && notificacion.estado === "FALLIDO_PERMANENTE" && (
                        seleccion === notificacion.id ? <form onSubmit={reencolar} className="mt-3 space-y-2">
                          <Field label="Contacto autorizado corregido" required>
                            <Input value={contacto} onChange={(e) => setContacto(e.target.value)} required />
                          </Field>
                          <p className="text-xs text-muted">Debe coincidir con el contacto actualizado de este usuario en el padrón.</p>
                          <Button type="submit" loading={busy}>Reencolar aviso</Button>
                        </form> : <Button variant="secondary" size="sm" onClick={() => {
                          setSeleccion(notificacion.id); setContacto(""); setError(null);
                        }}>Corregir y reencolar</Button>
                      )}
                    </div>
                    <Badge tone={estado.tone}>{estado.label}</Badge>
                  </li>
                );
              })}
            </ul>
          )}
        </CardBody>
      </Card>

      <AlertasEntrega
        condominioId={condominioId}
        isAuditor={isAuditor}
        version={versionAlertas}
      />
    </div>
  );
}
