"use client";

import { useEffect, useRef, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { EmptyState, Spinner } from "@/components/ui/Feedback";
import { Field, Input, Textarea } from "@/components/ui/Field";
import {
  ApiError, consultarExcepcion, listarExcepciones, resolverExcepcion,
  type AccionExcepcion, type DetalleExcepcion, type Excepcion, type PaginaExcepciones,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";

const TAMANO_PAGINA = 25;
const ESTADOS: Record<Excepcion["estado"], { etiqueta: string; tono: Tone }> = {
  ABIERTA: { etiqueta: "Abierta", tono: "warning" },
  EN_PROCESO: { etiqueta: "En proceso", tono: "info" },
  RESUELTA: { etiqueta: "Resuelta", tono: "success" },
  FALLIDA: { etiqueta: "Reenvío fallido", tono: "danger" },
};
const ACCIONES: Record<AccionExcepcion, string> = {
  REENVIAR_CORREO: "Reenviar correo",
  REINTENTAR_JOB: "Reintentar job",
  CERRAR_CON_MOTIVO: "Cerrar caso",
};
const RESULTADOS: Record<string, string> = {
  EN_COLA: "En cola",
  REINTENTANDO: "Reintentando",
  ENVIADO: "Aceptado por el proveedor",
  ENTREGADO: "Entregado",
  FALLIDO_PERMANENTE: "Fallo definitivo",
  OMITIDO: "Omitido",
};

function EstadoCaso({ estado }: { estado: Excepcion["estado"] }) {
  return <Badge tone={ESTADOS[estado].tono}>{ESTADOS[estado].etiqueta}</Badge>;
}

export function ExcepcionesSection({ onRevisarCorreo }: { onRevisarCorreo: () => void }) {
  const [pagina, setPagina] = useState(0);
  const [revision, setRevision] = useState(0);
  const [seleccion, setSeleccion] = useState<string>();
  const [lista, setLista] = useState<PaginaExcepciones>();
  const [error, setError] = useState("");
  const actualizar = () => setRevision((actual) => actual + 1);

  useEffect(() => {
    const solicitud = new AbortController();
    setLista(undefined);
    setError("");
    listarExcepciones(pagina * TAMANO_PAGINA, TAMANO_PAGINA, solicitud.signal)
      .then((datos) => { if (!solicitud.signal.aborted) setLista(datos); })
      .catch(() => { if (!solicitud.signal.aborted) setError("No pudimos cargar las excepciones."); });
    return () => solicitud.abort();
  }, [pagina, revision]);

  function cambiarPagina(numero: number) {
    setSeleccion(undefined);
    setPagina(numero);
  }

  return (
    <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
      <Card>
        <CardHeader
          title="Fallos operativos"
          actions={<Button size="sm" variant="secondary" onClick={actualizar}>Actualizar</Button>}
        />
        {error ? <Alert className="m-4" tone="danger">{error}</Alert> : !lista ? (
          <Spinner className="m-4" label="Cargando excepciones…" />
        ) : lista.items.length === 0 ? (
          <EmptyState title="No hay excepciones en esta página" />
        ) : (
          <ul className="divide-y divide-line">
            {lista.items.map((caso) => (
              <li key={caso.id}>
                <button
                  type="button"
                  aria-pressed={caso.id === seleccion}
                  onClick={() => setSeleccion(caso.id)}
                  className="flex w-full flex-col gap-2 px-4 py-4 text-left hover:bg-canvas aria-pressed:bg-brand-50 sm:px-6"
                >
                  <span className="flex w-full flex-wrap items-center justify-between gap-2">
                    <span className="text-sm font-semibold">{caso.origen === "CORREO" ? "Correo" : "Tarea automática"}</span>
                    <EstadoCaso estado={caso.estado} />
                  </span>
                  <span className="break-words text-sm">{caso.causa}</span>
                  <span className="text-xs text-muted">
                    Prioridad {caso.prioridad.toLowerCase()} · {formatDateTime(caso.creada_en)}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        {lista && (pagina > 0 || lista.hay_mas) && (
          <nav className="flex justify-between gap-2 border-t border-line p-4" aria-label="Páginas de excepciones">
            <Button size="sm" variant="secondary" disabled={pagina === 0} onClick={() => cambiarPagina(pagina - 1)}>
              Anterior
            </Button>
            <Button size="sm" variant="secondary" disabled={!lista.hay_mas} onClick={() => cambiarPagina(pagina + 1)}>
              Siguiente
            </Button>
          </nav>
        )}
      </Card>
      {seleccion && (
        <DetalleCaso
          key={seleccion}
          id={seleccion}
          revision={revision}
          onActualizada={actualizar}
          onRevisarCorreo={onRevisarCorreo}
        />
      )}
    </div>
  );
}

function DetalleCaso({ id, revision, onActualizada, onRevisarCorreo }: {
  id: string; revision: number; onActualizada: () => void; onRevisarCorreo: () => void;
}) {
  const [caso, setCaso] = useState<DetalleExcepcion>();
  const [error, setError] = useState("");
  const [confirmacion, setConfirmacion] = useState("");

  useEffect(() => {
    const solicitud = new AbortController();
    setCaso(undefined);
    setError("");
    consultarExcepcion(id, solicitud.signal)
      .then((datos) => { if (!solicitud.signal.aborted) setCaso(datos); })
      .catch(() => { if (!solicitud.signal.aborted) setError("No pudimos cargar el detalle."); });
    return () => solicitud.abort();
  }, [id, revision]);

  return (
    <Card>
      <CardHeader title="Detalle del caso" actions={caso && <EstadoCaso estado={caso.estado} />} />
      <CardBody className="space-y-5">
        {error ? <Alert tone="danger">{error}</Alert> : !caso ? (
          <Spinner label="Cargando detalle…" />
        ) : (
          <>
            <p className="text-sm">{caso.causa}</p>
            {confirmacion && <Alert tone="success">{confirmacion}</Alert>}
            <dl className="grid gap-3 rounded-lg bg-canvas p-4 text-sm sm:grid-cols-2">
              <div>
                <dt className="text-muted">Ciclo del fallo</dt>
                <dd>{caso.evidencia.ciclo_fallido}</dd>
              </div>
              <div>
                <dt className="text-muted">{caso.origen === "JOB" ? "Estado del job" : "Resultado del envío"}</dt>
                <dd>{RESULTADOS[caso.evidencia.estado_operacion] ?? caso.evidencia.estado_operacion}</dd>
              </div>
              {caso.evidencia.referencia_correlacion && (
                <div className="sm:col-span-2">
                  <dt className="text-muted">Referencia de diagnóstico</dt>
                  <dd className="break-all font-medium">{caso.evidencia.referencia_correlacion}</dd>
                </div>
              )}
              {caso.historial[0] && (
                <div className="sm:col-span-2">
                  <dt className="text-muted">Resultado real de la última decisión</dt>
                  <dd className="break-all font-medium">
                    {caso.historial[0].efecto.estado_operacion ?? caso.historial[0].efecto.estado_proceso ?? "Registrado"}
                  </dd>
                </div>
              )}
            </dl>
            {caso.requiere_revision_correo && (
              <Alert
                tone="warning"
                title="Aceptación del envío incierta"
                action={<Button size="sm" variant="secondary" onClick={onRevisarCorreo}>Revisar en Comunicados</Button>}
              >
                Comprueba el intento en el flujo de revisión de correo.
              </Alert>
            )}
            {caso.acciones_permitidas.length > 0 && (
              <DecidirCaso caso={caso} onGuardada={(mensaje) => {
                setConfirmacion(mensaje);
                onActualizada();
              }} />
            )}
            {caso.historial.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-semibold">Historial de decisiones</h3>
                <ul className="space-y-3">
                  {caso.historial.map((registro) => (
                    <li key={registro.id} className="border-l-2 border-line pl-3 text-sm">
                      <p className="font-medium">{ACCIONES[registro.accion]} · {formatDateTime(registro.fecha)}</p>
                      <p className="whitespace-pre-wrap break-words">{registro.motivo}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card>
  );
}

function DecidirCaso({ caso, onGuardada }: { caso: DetalleExcepcion; onGuardada: (mensaje: string) => void }) {
  const [accion, setAccion] = useState<AccionExcepcion>();
  const [motivo, setMotivo] = useState("");
  const [contacto, setContacto] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const bloqueado = useRef(false);
  const clave = useRef<{ solicitud: string; id: string }>();
  const email = useRef<HTMLInputElement>(null);
  const reenvio = accion === "REENVIAR_CORREO";

  async function confirmar() {
    if (!accion || bloqueado.current) return;
    if (!motivo.trim()) { setError("Ingresa el motivo de la decisión."); return; }
    if (reenvio && !email.current?.reportValidity()) return;
    const datos = { accion, motivo: motivo.trim(), ...(reenvio && { nuevo_destinatario: contacto.trim() }) };
    const solicitud = JSON.stringify(datos);
    if (clave.current?.solicitud !== solicitud) clave.current = { solicitud, id: crypto.randomUUID() };
    bloqueado.current = true;
    setGuardando(true);
    setError("");
    try {
      await resolverExcepcion(caso.id, datos, clave.current.id);
      setAccion(undefined);
      onGuardada(
        reenvio
          ? "Reenvío en cola. Actualiza para consultar el resultado."
          : accion === "REINTENTAR_JOB"
            ? "Job marcado para reintento. Actualiza para ver el resultado."
            : "Caso cerrado.",
      );
    } catch (causa) {
      setError(causa instanceof ApiError ? causa.message : "No pudimos registrar la decisión. Inténtalo de nuevo.");
    } finally {
      bloqueado.current = false;
      setGuardando(false);
    }
  }

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {caso.acciones_permitidas.map((opcion) => (
          <Button key={opcion} variant={opcion === "CERRAR_CON_MOTIVO" ? "secondary" : "primary"} onClick={() => {
            setAccion(opcion);
            setError("");
          }}>
            {ACCIONES[opcion]}
          </Button>
        ))}
      </div>
      <ConfirmDialog
        open={!!accion}
        title={accion ? ACCIONES[accion] : "Resolver excepción"}
        tone={reenvio ? "primary" : "danger"}
        confirmLabel={reenvio ? "Poner en cola" : "Confirmar cierre"}
        loading={guardando}
        onCancel={() => { if (!guardando) setAccion(undefined); }}
        onConfirm={() => void confirmar()}
      >
        {error && <Alert tone="danger">{error}</Alert>}
        {reenvio && (
          <Field label="Correo corregido" hint="Usa el contacto autorizado del destinatario." required>
            <Input ref={email} type="email" value={contacto} maxLength={320} onChange={(event) => setContacto(event.target.value)} />
          </Field>
        )}
        <Field label="Motivo" required>
          <Textarea value={motivo} onChange={(event) => setMotivo(event.target.value)} maxLength={500} />
        </Field>
      </ConfirmDialog>
    </>
  );
}
