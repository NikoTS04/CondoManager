"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import { AlertTriangle, CheckCircle2, History, RefreshCw, RotateCcw, Send } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import {
  atenderAlertaNotificacion,
  fetchAlertasNotificaciones,
  fetchNotificacionDetalle,
  reenviarNotificacion,
  type AlertaAdministrativa,
  type CanalNotificacion,
  type Departamento,
  type EstadoNotificacion,
  type NotificacionDetalle,
  type NotificacionLog,
  type OrigenNotificacion,
} from "@/lib/api";
import { formatDate } from "@/lib/format";

export interface ComunicadosSectionProps {
  loading: boolean;
  notificaciones: NotificacionLog[];
  isAuditor: boolean;
  titulo: string;
  mensaje: string;
  canal?: CanalNotificacion;
  condominioId?: string | null;
  departamentos?: Departamento[];
  alertas?: AlertaAdministrativa[];
  error?: string | null;
  onTituloChange: (value: string) => void;
  onMensajeChange: (value: string) => void;
  onCanalChange?: (value: CanalNotificacion) => void;
  onSubmit: (event: FormEvent) => void;
  onRetry?: () => void;
  onRefresh?: () => Promise<void> | void;
}

export const ESTADOS_NOTIFICACION: Record<
  EstadoNotificacion,
  { label: string; tone: Tone }
> = {
  ENTREGADO: { label: "Entregado", tone: "success" },
  ACEPTADO: { label: "Aceptado", tone: "info" },
  REINTENTANDO: { label: "Reintentando", tone: "warning" },
  FALLIDO_PERMANENTE: { label: "Fallido permanente", tone: "danger" },
  EN_COLA: { label: "En cola", tone: "neutral" },
};

const ORIGENES_OPCIONES: { value: OrigenNotificacion; label: string }[] = [
  { value: "COMUNICADO", label: "Comunicado" },
  { value: "CUOTA", label: "Cuota" },
  { value: "COMPROBANTE", label: "Comprobante" },
  { value: "RESERVA", label: "Reserva" },
  { value: "USUARIO", label: "Usuario" },
];

export function ComunicadosSection({
  loading,
  notificaciones,
  isAuditor,
  titulo,
  mensaje,
  canal = "EMAIL",
  condominioId,
  departamentos = [],
  alertas: alertasProp,
  error = null,
  onTituloChange,
  onMensajeChange,
  onCanalChange,
  onSubmit,
  onRetry,
  onRefresh,
}: ComunicadosSectionProps) {
  const [filtroDepartamento, setFiltroDepartamento] = useState<string>("");
  const [filtroEstado, setFiltroEstado] = useState<string>("");
  const [filtroCanal, setFiltroCanal] = useState<string>("");
  const [filtroOrigen, setFiltroOrigen] = useState<string>("");

  const [alertasInternas, setAlertasInternas] = useState<AlertaAdministrativa[]>([]);
  const [cargandoAlertas, setCargandoAlertas] = useState(false);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [mensajeAccion, setMensajeAccion] = useState<string | null>(null);
  const [procesandoId, setProcesandoId] = useState<string | null>(null);

  const [destinatariosEdicion, setDestinatariosEdicion] = useState<Record<string, string>>({});
  const [detalleAbiertoId, setDetalleAbiertoId] = useState<string | null>(null);
  const [detallesCache, setDetallesCache] = useState<Record<string, NotificacionDetalle>>({});
  const [cargandoDetalleId, setCargandoDetalleId] = useState<string | null>(null);

  useEffect(() => {
    if (alertasProp !== undefined) return;
    if (!condominioId) {
      setAlertasInternas([]);
      return;
    }
    let cancelado = false;
    setCargandoAlertas(true);
    fetchAlertasNotificaciones(condominioId, true)
      .then((lista) => {
        if (!cancelado) setAlertasInternas(lista);
      })
      .catch(() => {
        if (!cancelado) setAlertasInternas([]);
      })
      .finally(() => {
        if (!cancelado) setCargandoAlertas(false);
      });
    return () => {
      cancelado = true;
    };
  }, [condominioId, alertasProp, notificaciones]);

  const alertasAbiertas = useMemo(() => {
    const base = alertasProp ?? alertasInternas;
    return base.filter((a) => !a.atendida_en);
  }, [alertasProp, alertasInternas]);

  const notificacionesFiltradas = useMemo(() => {
    return notificaciones.filter((item) => {
      if (filtroDepartamento && item.departamento_id !== filtroDepartamento) return false;
      if (filtroEstado && item.estado !== filtroEstado) return false;
      if (filtroCanal && item.canal !== filtroCanal) return false;
      if (filtroOrigen && item.origen_tipo !== filtroOrigen) return false;
      return true;
    });
  }, [notificaciones, filtroDepartamento, filtroEstado, filtroCanal, filtroOrigen]);

  async function manejarAtenderAlerta(alertaId: string) {
    setProcesandoId(alertaId);
    setErrorAccion(null);
    setMensajeAccion(null);
    const res = await atenderAlertaNotificacion(alertaId);
    setProcesandoId(null);
    if (!res.ok) {
      setErrorAccion(res.error ?? "No se pudo marcar la alerta como atendida.");
      return;
    }
    setAlertasInternas((prev) => prev.filter((a) => a.id !== alertaId));
    setMensajeAccion("Alerta administrativa marcada como atendida.");
    if (onRefresh) await onRefresh();
  }

  async function manejarReenvio(notificacion: NotificacionLog) {
    setProcesandoId(notificacion.id);
    setErrorAccion(null);
    setMensajeAccion(null);
    const nuevoDestinatario = destinatariosEdicion[notificacion.id];
    const res = await reenviarNotificacion(notificacion.id, nuevoDestinatario);
    setProcesandoId(null);
    if (!res.ok) {
      setErrorAccion(res.error ?? "No se pudo reprogramar la notificación.");
      return;
    }
    setMensajeAccion("Notificación reprogramada en cola para reenvío.");
    setDetallesCache((prev) => {
      const copia = { ...prev };
      delete copia[notificacion.id];
      return copia;
    });
    if (onRefresh) await onRefresh();
  }

  async function alternarDetalle(notificacionId: string) {
    if (detalleAbiertoId === notificacionId) {
      setDetalleAbiertoId(null);
      return;
    }
    setDetalleAbiertoId(notificacionId);
    if (detallesCache[notificacionId]) return;
    setCargandoDetalleId(notificacionId);
    try {
      const detalle = await fetchNotificacionDetalle(notificacionId);
      setDetallesCache((prev) => ({ ...prev, [notificacionId]: detalle }));
    } catch (err) {
      setErrorAccion(
        err instanceof Error ? err.message : "No se pudo cargar el historial de intentos."
      );
    } finally {
      setCargandoDetalleId(null);
    }
  }

  const mapaDepartamentos = useMemo(() => {
    const mapa = new Map<string, string>();
    for (const dpto of departamentos) {
      mapa.set(dpto.id, dpto.numero);
    }
    return mapa;
  }, [departamentos]);

  return (
    <div className="space-y-6">
      {(alertasAbiertas.length > 0 || cargandoAlertas) && (
        <Card>
          <CardHeader
            title={`Alertas administrativas abiertas (${alertasAbiertas.length})`}
            description="Notificaciones que agotaron sus intentos de entrega y requieren revisión."
            icon={<AlertTriangle className="h-5 w-5 text-danger-600" aria-hidden />}
          />
          <CardBody>
            {cargandoAlertas && alertasAbiertas.length === 0 ? (
              <SkeletonList rows={1} label="Cargando alertas administrativas" />
            ) : (
              <ul className="divide-y divide-line">
                {alertasAbiertas.map((alerta) => (
                  <li
                    key={alerta.id}
                    className="flex flex-wrap items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
                  >
                    <div className="space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge tone={alerta.severidad === "ALTA" ? "danger" : "warning"}>
                          {alerta.severidad}
                        </Badge>
                        <span className="text-xs font-medium text-muted">{alerta.tipo}</span>
                        <span className="text-xs text-muted">· {formatDate(alerta.creado_en)}</span>
                      </div>
                      <p className="text-sm text-ink">{alerta.mensaje}</p>
                    </div>
                    {!isAuditor && (
                      <Button
                        variant="secondary"
                        size="sm"
                        loading={procesandoId === alerta.id}
                        icon={<CheckCircle2 className="h-4 w-4" aria-hidden />}
                        onClick={() => void manejarAtenderAlerta(alerta.id)}
                      >
                        Marcar atendida
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      )}

      {errorAccion && (
        <Alert tone="danger" title="Operación no completada" onDismiss={() => setErrorAccion(null)}>
          {errorAccion}
        </Alert>
      )}

      {mensajeAccion && (
        <Alert tone="success" title="Actualización" onDismiss={() => setMensajeAccion(null)}>
          {mensajeAccion}
        </Alert>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <Card>
          <CardHeader
            title="Comunicado a la comunidad"
            description="Redacta un aviso para los residentes con vínculo activo del condominio."
          />
          <CardBody>
            {isAuditor ? (
              <div className="rounded-lg border border-audit-200 bg-audit-50 p-3">
                <Badge tone="audit">Solo lectura</Badge>
                <p className="mt-2 text-sm text-audit-800">
                  El envío de comunicados y el reenvío manual no están disponibles para auditoría.
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
                {onCanalChange && (
                  <Field label="Canal de envío">
                    <Select
                      value={canal}
                      onChange={(event) =>
                        onCanalChange(event.target.value as CanalNotificacion)
                      }
                    >
                      <option value="EMAIL">Correo electrónico (EMAIL)</option>
                      <option value="WHATSAPP">WhatsApp</option>
                    </Select>
                  </Field>
                )}
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
          <CardHeader
            title="Bitácora de notificaciones"
            description="Trazabilidad persistente de envíos automáticos y comunicados."
            actions={
              onRefresh ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void onRefresh()}
                  icon={<RefreshCw className="h-4 w-4" aria-hidden />}
                >
                  Refrescar
                </Button>
              ) : undefined
            }
          />
          <CardBody className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <Field label="Departamento">
                <Select
                  value={filtroDepartamento}
                  onChange={(e) => setFiltroDepartamento(e.target.value)}
                >
                  <option value="">Todos</option>
                  {departamentos.map((dpto) => (
                    <option key={dpto.id} value={dpto.id}>
                      Dpto. {dpto.numero}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Estado">
                <Select
                  value={filtroEstado}
                  onChange={(e) => setFiltroEstado(e.target.value)}
                >
                  <option value="">Todos</option>
                  <option value="EN_COLA">En cola</option>
                  <option value="REINTENTANDO">Reintentando</option>
                  <option value="ACEPTADO">Aceptado</option>
                  <option value="ENTREGADO">Entregado</option>
                  <option value="FALLIDO_PERMANENTE">Fallido permanente</option>
                </Select>
              </Field>
              <Field label="Canal">
                <Select
                  value={filtroCanal}
                  onChange={(e) => setFiltroCanal(e.target.value)}
                >
                  <option value="">Todos</option>
                  <option value="EMAIL">EMAIL</option>
                  <option value="WHATSAPP">WHATSAPP</option>
                </Select>
              </Field>
              <Field label="Origen">
                <Select
                  value={filtroOrigen}
                  onChange={(e) => setFiltroOrigen(e.target.value)}
                >
                  <option value="">Todos</option>
                  {ORIGENES_OPCIONES.map((op) => (
                    <option key={op.value} value={op.value}>
                      {op.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            {loading ? (
              <SkeletonList rows={3} label="Cargando bitácora de notificaciones" />
            ) : error ? (
              <Alert
                tone="danger"
                title="No se pudo cargar la bitácora de notificaciones"
                action={
                  onRetry ? (
                    <Button variant="secondary" size="sm" onClick={onRetry}>
                      Reintentar
                    </Button>
                  ) : undefined
                }
              >
                {error}
              </Alert>
            ) : notificacionesFiltradas.length === 0 ? (
              <EmptyState
                title="Sin envíos registrados"
                description="No hay notificaciones que coincidan con los filtros seleccionados."
              />
            ) : (
              <ul className="divide-y divide-line">
                {notificacionesFiltradas.map((notificacion) => {
                  const estado = ESTADOS_NOTIFICACION[notificacion.estado] ?? {
                    label: notificacion.estado,
                    tone: "neutral" as Tone,
                  };
                  const fechaMostrar = notificacion.creado_en;
                  const unidadNumero = notificacion.departamento_id
                    ? mapaDepartamentos.get(notificacion.departamento_id)
                    : null;
                  const detalle = detallesCache[notificacion.id];
                  const abierto = detalleAbiertoId === notificacion.id;

                  return (
                    <li key={notificacion.id} className="space-y-3 py-3.5 first:pt-0 last:pb-0">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="space-y-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <p className="font-medium text-ink">
                              {notificacion.asunto || notificacion.tipo_evento}
                            </p>
                            {notificacion.origen_tipo && (
                              <Badge tone="neutral">{notificacion.origen_tipo}</Badge>
                            )}
                            {notificacion.transporte_simulado && (
                              <Badge tone="warning">Transporte simulado</Badge>
                            )}
                          </div>
                          <p className="text-xs text-muted">
                            {notificacion.destinatario} · {notificacion.canal}
                            {unidadNumero ? ` · Dpto. ${unidadNumero}` : ""} ·{" "}
                            {formatDate(fechaMostrar)}
                          </p>
                          <p className="text-xs text-muted">
                            Ciclo: {notificacion.ciclo ?? 1} · Intentos:{" "}
                            {notificacion.intentos}
                            {notificacion.max_intentos
                              ? ` / ${notificacion.max_intentos}`
                              : " / 4"}
                            {notificacion.proximo_intento_en &&
                            notificacion.estado === "REINTENTANDO"
                              ? ` · Próximo intento: ${formatDate(notificacion.proximo_intento_en)}`
                              : ""}
                          </p>
                          {notificacion.error_mensaje && (
                            <p className="text-xs font-medium text-danger-700">
                              Error ({notificacion.error_codigo || "FALLO"}):{" "}
                              {notificacion.error_mensaje}
                            </p>
                          )}
                        </div>

                        <div className="flex flex-wrap items-center gap-2">
                          <Badge tone={estado.tone}>{estado.label}</Badge>
                          <Button
                            variant="secondary"
                            size="sm"
                            icon={<History className="h-3.5 w-3.5" aria-hidden />}
                            onClick={() => void alternarDetalle(notificacion.id)}
                          >
                            {abierto ? "Ocultar intentos" : "Ver intentos"}
                          </Button>
                        </div>
                      </div>

                      {notificacion.estado === "FALLIDO_PERMANENTE" && !isAuditor && (
                        <div className="flex flex-wrap items-end gap-2 rounded-lg border border-danger-200 bg-danger-50/40 p-3">
                          <div className="min-w-[220px] flex-1">
                            <Field label="Nuevo destinatario (opcional)">
                              <Input
                                placeholder={notificacion.destinatario}
                                value={destinatariosEdicion[notificacion.id] ?? ""}
                                onChange={(e) =>
                                  setDestinatariosEdicion((prev) => ({
                                    ...prev,
                                    [notificacion.id]: e.target.value,
                                  }))
                                }
                              />
                            </Field>
                          </div>
                          <Button
                            variant="secondary"
                            size="sm"
                            loading={procesandoId === notificacion.id}
                            icon={<RotateCcw className="h-4 w-4" aria-hidden />}
                            onClick={() => void manejarReenvio(notificacion)}
                          >
                            Reenviar
                          </Button>
                        </div>
                      )}

                      {abierto && (
                        <div className="rounded-lg border border-line bg-slate-50 p-3 text-xs space-y-2">
                          <p className="font-semibold text-ink">
                            Historial de intentos de entrega
                          </p>
                          {cargandoDetalleId === notificacion.id ? (
                            <p className="text-muted">Cargando intentos…</p>
                          ) : !detalle || detalle.historial_intentos.length === 0 ? (
                            <p className="text-muted">
                              Aún no se registran intentos de transporte para esta notificación.
                            </p>
                          ) : (
                            <ul className="divide-y divide-line">
                              {detalle.historial_intentos.map((intento) => (
                                <li
                                  key={intento.id}
                                  className="py-1.5 flex flex-wrap items-center justify-between gap-2"
                                >
                                  <div>
                                    <span className="font-medium">
                                      Ciclo #{intento.ciclo} · Intento #{intento.numero}
                                    </span>{" "}
                                    · {intento.resultado} · {intento.transporte}
                                    {intento.transporte_simulado
                                      ? " (simulado)"
                                      : ""}
                                    {intento.detalle
                                      ? ` — ${intento.detalle}`
                                      : ""}
                                  </div>
                                  <span className="text-muted">
                                    {formatDate(intento.finalizado_en)}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          )}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
