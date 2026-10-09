"use client";

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { useAuth } from "@/context/AuthContext";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { Field, Textarea } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { SkeletonList } from "@/components/ui/Feedback";
import { ComunicadosSection } from "@/features/junta/ComunicadosSection";
import { ConciliacionSection } from "@/features/junta/ConciliacionSection";
import { CuotasSection } from "@/features/junta/CuotasSection";
import { AsistenteEmision } from "@/features/junta/AsistenteEmision";
import { distribucionValida } from "@/features/junta/calculos";
import { EstructuraCondominio } from "@/features/junta/EstructuraCondominio";
import { JuntaNav, JUNTA_NAV_ITEMS, type JuntaSection } from "@/features/junta/JuntaNav";
import { MorasSection } from "@/features/junta/MorasSection";
import { PresupuestoMensual, type PresupuestoAprobado } from "@/features/junta/PresupuestoMensual";
import { ResumenSection } from "@/features/junta/ResumenSection";
import ConfiguracionCondominio from "@/features/junta/ConfiguracionCondominio";
import {
  conciliarComprobante,
  emitirLoteCuotas,
  enviarComunicadoMasivo,
  fetchComprobantes,
  fetchDepartamentos,
  fetchNotificaciones,
  type ComprobantePago,
  type Departamento,
  type NotificacionLog,
} from "@/lib/api";
import { isPositiveMoney, normalizeMoney } from "@/lib/money";
import { RefreshCw } from "lucide-react";

type Confirmacion =
  | { kind: "emitir" }
  | { kind: "comprobante"; id: string; decision: "APROBADO" | "RECHAZADO" }
  | { kind: "comunicado" };

export default function JuntaPortal() {
  const { user } = useAuth();
  const isAuditor = user?.rol === "AUDITOR";
  const isSuperAdmin = user?.rol === "SUPERADMIN";

  const [section, setSection] = useState<JuntaSection>("resumen");
  const [comprobantes, setComprobantes] = useState<ComprobantePago[]>([]);
  const [departamentos, setDepartamentos] = useState<Departamento[]>([]);
  const [notificaciones, setNotificaciones] = useState<NotificacionLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [presupuesto, setPresupuesto] = useState<PresupuestoAprobado | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [titulo, setTitulo] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [confirmacion, setConfirmacion] = useState<Confirmacion | null>(null);
  const [motivo, setMotivo] = useState("");
  const [busy, setBusy] = useState(false);
  const [morasFeedback, setMorasFeedback] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    setLoadError(null);

    try {
      const [nuevosComprobantes, nuevosDepartamentos, nuevasNotificaciones] = await Promise.all([
        fetchComprobantes(),
        fetchDepartamentos(),
        fetchNotificaciones(),
      ]);
      setComprobantes(nuevosComprobantes);
      setDepartamentos(nuevosDepartamentos);
      setNotificaciones(nuevasNotificaciones);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "No se pudieron cargar los datos.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const pendientes = useMemo(
    () => comprobantes.filter((comprobante) => comprobante.estado === "EN_REVISION"),
    [comprobantes],
  );
  const presupuestoActual = presupuesto;
  const alicuotasValidas = distribucionValida(
    departamentos.map((departamento) => departamento.coeficiente),
  );
  const navActual = JUNTA_NAV_ITEMS.find((item) => item.id === section);

  function aprobarPresupuesto(nuevoPresupuesto: PresupuestoAprobado) {
    setPresupuesto(nuevoPresupuesto);
    setFeedback(null);
  }

  function solicitarEmision(event: FormEvent) {
    event.preventDefault();
    if (!presupuestoActual) {
      setFeedback("Aprueba el presupuesto antes de emitir las cuotas.");
      return;
    }
    if (!isPositiveMoney(presupuestoActual.montoTotal)) {
      setFeedback("El total aprobado debe ser un monto mayor que cero.");
      return;
    }
    if (!alicuotasValidas) {
      setFeedback("La distribución debe sumar 100.0000 % antes de emitir.");
      return;
    }

    setPresupuesto({
      ...presupuestoActual,
      montoTotal: normalizeMoney(presupuestoActual.montoTotal),
    });
    setConfirmacion({ kind: "emitir" });
  }

  function solicitarComunicado(event: FormEvent) {
    event.preventDefault();
    if (titulo.trim() && mensaje.trim()) {
      setConfirmacion({ kind: "comunicado" });
    }
  }

  async function confirmarAccion() {
    if (!confirmacion) return;
    if (
      confirmacion.kind === "comprobante" &&
      confirmacion.decision === "RECHAZADO" &&
      !motivo.trim()
    ) {
      setFeedback("Indica el motivo para rechazar el comprobante.");
      return;
    }

    setBusy(true);
    try {
      if (confirmacion.kind === "emitir" && presupuestoActual) {
        const resultado = await emitirLoteCuotas(
          presupuestoActual.periodo,
          presupuestoActual.montoTotal,
        );
        setFeedback(resultado.ok
          ? `Emisión de ${presupuestoActual.periodo} completada para ${departamentos.length} departamentos.`
          : `No se pudo emitir: ${resultado.error}`);
      } else if (confirmacion.kind === "comprobante") {
        const resultado = await conciliarComprobante(
          confirmacion.id,
          confirmacion.decision,
          confirmacion.decision === "RECHAZADO" ? motivo.trim() : undefined,
        );
        if (resultado.ok) {
          setFeedback("La conciliación del comprobante se actualizó correctamente.");
          await loadData();
        } else {
          setFeedback(resultado.error || "No se pudo procesar el comprobante.");
        }
      } else if (confirmacion.kind === "comunicado") {
        const resultado = await enviarComunicadoMasivo(titulo, mensaje);
        if (resultado.ok) {
          const alcance = resultado.generadas ?? 0;
          setFeedback(
            alcance > 0
              ? `Comunicado enviado a ${alcance} destinatarios.`
              : "Comunicado enviado correctamente.",
          );
          setTitulo("");
          setMensaje("");
          await loadData();
        } else {
          setFeedback("No se pudo enviar el comunicado.");
        }
      }
    } catch (error) {
      setFeedback(error instanceof Error ? error.message : "No se pudo completar la acción.");
    } finally {
      setBusy(false);
      setConfirmacion(null);
      setMotivo("");
    }
  }

  function evaluarMorasSimuladas() {
    setMorasFeedback(
      "Simulación local: se aplicaron las reglas de gracia; " +
      "una unidad permanece en mora y otra fue postergada por tener un comprobante en revisión. " +
      "No se llamó al backend.",
    );
  }

  const seccionTitulo = navActual?.label ?? "Resumen";
  const comprobanteConfirmado = confirmacion?.kind === "comprobante"
    ? comprobantes.find((comprobante) => comprobante.id === confirmacion.id)
    : undefined;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Portal de Junta"
        description={`Villa Bonita 3 · ${seccionTitulo}`}
        actions={(
          <Button
            variant="secondary"
            onClick={() => void loadData()}
            icon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}
          >
            Actualizar
          </Button>
        )}
      />

      {isAuditor && (
        <div className="rounded-xl border border-audit-200 bg-audit-50 p-4 text-audit-800">
          <Badge tone="audit">Solo lectura</Badge>
          <p className="mt-2 text-sm">
            Las acciones de escritura no están disponibles en modo auditor.
          </p>
        </div>
      )}

      <div className="lg:grid lg:grid-cols-[230px_minmax(0,1fr)] lg:gap-6">
        <aside className="mb-4 lg:mb-0">
          <div className="lg:sticky lg:top-4">
            <JuntaNav
              section={section}
              isSuperAdmin={isSuperAdmin}
              pendientes={pendientes.length}
              onNavigate={setSection}
            />
          </div>
        </aside>

        <div id="main-content" className="min-w-0 space-y-6">
          {loadError && (
            <Alert
              tone="danger"
              title="No se pudieron cargar los datos"
              action={(
                <Button variant="secondary" onClick={() => void loadData()}>
                  Reintentar
                </Button>
              )}
            >
              {loadError}
            </Alert>
          )}
          {feedback && (
            <Alert
              tone={feedback.includes("No se pudo") || feedback.startsWith("Indica") ? "danger" : "success"}
              title="Resultado"
              onDismiss={() => setFeedback(null)}
            >
              {feedback}
            </Alert>
          )}

          {section === "resumen" && (
            <ResumenSection
              loading={loading}
              departamentos={departamentos.length}
              comprobantesPendientes={pendientes.length}
              presupuesto={presupuesto}
              onNavigate={setSection}
            />
          )}
          {section === "configuracion" && isSuperAdmin && (
            <ConfiguracionCondominio puedeEditar={isSuperAdmin} />
          )}
          {section === "estructura" && (
            <EstructuraCondominio
              departamentosIniciales={departamentos}
              soloLectura={isAuditor}
              cargando={loading}
            />
          )}
          {section === "presupuesto" && (
            <>
              <AsistenteEmision
                paso={presupuesto ? 2 : 1}
                presupuestoAprobado={presupuesto !== null}
                distribucionAprobada={alicuotasValidas}
              />
              <PresupuestoMensual
                condominioId={user?.condominio_id || "vb3-condo"}
                puedeEditar={!isAuditor}
                onAprobar={aprobarPresupuesto}
              />
            </>
          )}
          {section === "cuotas" && (
            <>
              <AsistenteEmision
                paso={!presupuesto ? 1 : alicuotasValidas ? 3 : 2}
                presupuestoAprobado={presupuesto !== null}
                distribucionAprobada={alicuotasValidas}
              />
              <CuotasSection
                departamentos={departamentos}
                periodo={presupuesto?.periodo ?? "—"}
                presupuesto={presupuesto}
                isAuditor={isAuditor}
                busy={busy}
                onEmit={solicitarEmision}
              />
            </>
          )}
          {section === "conciliacion" && (
            <ConciliacionSection
              loading={loading}
              comprobantes={comprobantes}
              isAuditor={isAuditor}
              onDecide={(id, decision) => {
                setMotivo("");
                setConfirmacion({ kind: "comprobante", id, decision });
              }}
            />
          )}
          {section === "moras" && (
            <MorasSection
              isAuditor={isAuditor}
              feedback={morasFeedback}
              onEvaluate={evaluarMorasSimuladas}
            />
          )}
          {section === "comunicados" && (
            <ComunicadosSection
              loading={loading}
              notificaciones={notificaciones}
              isAuditor={isAuditor}
              titulo={titulo}
              mensaje={mensaje}
              onTituloChange={setTitulo}
              onMensajeChange={setMensaje}
              onSubmit={solicitarComunicado}
            />
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmacion !== null}
        title={tituloConfirmacion(confirmacion)}
        confirmLabel={etiquetaConfirmacion(confirmacion)}
        tone={confirmacion?.kind === "comprobante" && confirmacion.decision === "RECHAZADO"
          ? "danger"
          : "primary"}
        loading={busy}
        onCancel={() => {
          setConfirmacion(null);
          setMotivo("");
        }}
        onConfirm={() => void confirmarAccion()}
      >
        {confirmacion?.kind === "emitir" && presupuesto && (
          <p>
            Se emitirán cuotas por un total de{" "}
            <MoneyAmount value={presupuesto.montoTotal} moneda={presupuesto.moneda} />{" "}
            para el periodo {presupuesto.periodo}, distribuidas entre {departamentos.length} departamentos.
          </p>
        )}
        {confirmacion?.kind === "comprobante" && (
          <div className="space-y-3">
            <p>
              Comprobante del departamento {comprobanteConfirmado?.departamento_id}: {" "}
              {comprobanteConfirmado
                ? <MoneyAmount value={comprobanteConfirmado.monto} />
                : "—"}. La decisión actualizará su estado contable.
            </p>
            {confirmacion.decision === "RECHAZADO" && (
              <Field label="Motivo del rechazo" required>
                <Textarea
                  autoFocus
                  value={motivo}
                  onChange={(event) => setMotivo(event.target.value)}
                  rows={3}
                />
              </Field>
            )}
          </div>
        )}
        {confirmacion?.kind === "comunicado" && (
          <p>
            Se enviará “{titulo}” a los {departamentos.length} departamentos registrados.
          </p>
        )}
      </ConfirmDialog>
    </div>
  );
}

function tituloConfirmacion(confirmacion: Confirmacion | null) {
  if (!confirmacion) return "Confirmar acción";
  if (confirmacion.kind === "emitir") return "Emitir cuotas";
  if (confirmacion.kind === "comunicado") return "Enviar comunicado masivo";
  return confirmacion.decision === "APROBADO" ? "Aprobar comprobante" : "Rechazar comprobante";
}

function etiquetaConfirmacion(confirmacion: Confirmacion | null) {
  if (!confirmacion) return "Confirmar";
  if (confirmacion.kind === "emitir") return "Emitir cuotas";
  if (confirmacion.kind === "comunicado") return "Enviar comunicado";
  return confirmacion.decision === "APROBADO" ? "Aprobar comprobante" : "Rechazar comprobante";
}
