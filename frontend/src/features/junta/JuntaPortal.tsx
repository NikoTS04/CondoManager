"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from "react";
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
import { UsuariosSection } from "@/features/junta/UsuariosSection";
import { AreasSection } from "@/features/junta/AreasSection";
import {
  conciliarComprobante,
  emitirLoteCuotas,
  enviarComunicadoMasivo,
  fetchComprobantes,
  listarDepartamentos,
  departamentoParaPortal,
  fetchNotificaciones,
  listarCondominios,
  type CanalNotificacion,
  type ComprobantePago,
  type DepartamentoRegistrado,
  type NotificacionLog,
} from "@/lib/api";
import { isPositiveMoney, normalizeMoney } from "@/lib/money";
import { RefreshCw } from "lucide-react";

type Confirmacion =
  | { kind: "emitir" }
  | { kind: "comprobante"; id: string; decision: "APROBADO" | "RECHAZADO" | "OBSERVADO" }
  | { kind: "comunicado" };

export default function JuntaPortal() {
  const { user } = useAuth();
  const isAuditor = user?.rol === "AUDITOR";
  const isSuperAdmin = user?.rol === "SUPERADMIN";

  const [section, setSection] = useState<JuntaSection>("resumen");
  const [comprobantes, setComprobantes] = useState<ComprobantePago[]>([]);
  const [departamentosRegistrados, setDepartamentosRegistrados] = useState<DepartamentoRegistrado[]>([]);
  const departamentos = useMemo(() => departamentosRegistrados.filter((d) => d.activo).map(departamentoParaPortal), [departamentosRegistrados]);
  const [notificaciones, setNotificaciones] = useState<NotificacionLog[]>([]);
  const [condominioActivoId, setCondominioActivoId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [presupuesto, setPresupuesto] = useState<PresupuestoAprobado | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [titulo, setTitulo] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [canalComunicado, setCanalComunicado] = useState<CanalNotificacion>("EMAIL");
  const [confirmacion, setConfirmacion] = useState<Confirmacion | null>(null);
  const [motivo, setMotivo] = useState("");
  const [busy, setBusy] = useState(false);
  const [morasFeedback, setMorasFeedback] = useState<string | null>(null);
  const cargaActual = useRef(0);
  const contextoActual = useRef(condominioActivoId);
  contextoActual.current = condominioActivoId;

  const loadData = useCallback(async () => {
    if (contextoActual.current !== condominioActivoId) return;
    const solicitud = ++cargaActual.current;
    setLoading(true);
    setLoadError(null);

    try {
      const [nuevosComprobantes, nuevosDepartamentos, nuevasNotificaciones] = await Promise.all([
        condominioActivoId ? fetchComprobantes(condominioActivoId) : Promise.resolve([]),
        condominioActivoId ? listarDepartamentos(condominioActivoId) : Promise.resolve([]),
        condominioActivoId ? fetchNotificaciones(condominioActivoId) : Promise.resolve([]),
      ]);
      if (solicitud !== cargaActual.current) return;
      setComprobantes(nuevosComprobantes);
      setDepartamentosRegistrados(nuevosDepartamentos);
      setNotificaciones(nuevasNotificaciones);
    } catch (error) {
      if (solicitud === cargaActual.current) setLoadError(error instanceof Error ? error.message : "No se pudieron cargar los datos.");
    } finally {
      if (solicitud === cargaActual.current) setLoading(false);
    }
  }, [condominioActivoId]);

  useEffect(() => {
    void loadData();
    const contador = cargaActual;
    return () => { contador.current++; };
  }, [loadData]);

  const seleccionarCondominio = useCallback((condominioId: string | null) => {
    cargaActual.current++;
    setDepartamentosRegistrados([]);
    setComprobantes([]);
    setNotificaciones([]);
    setCondominioActivoId(condominioId);
    setPresupuesto(null);
    if (condominioId) {
      localStorage.setItem("condo_active_id", condominioId);
    } else {
      localStorage.removeItem("condo_active_id");
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    if (user.rol !== "SUPERADMIN") {
      seleccionarCondominio(user.condominio_id);
      return;
    }

    let cancelado = false;
    async function resolverContextoSuperadmin() {
      const guardado = localStorage.getItem("condo_active_id");
      const resultado = await listarCondominios();
      if (cancelado) return;
      if (!resultado.ok || !resultado.data) {
        setCondominioActivoId(guardado);
        return;
      }

      const guardadoValido = resultado.data.some((item) => item.id === guardado);
      const seleccionado = guardadoValido
        ? guardado
        : resultado.data.length === 1
          ? resultado.data[0].id
          : null;
      seleccionarCondominio(seleccionado);
    }

    void resolverContextoSuperadmin();
    return () => {
      cancelado = true;
    };
  }, [seleccionarCondominio, user]);

  const pendientes = useMemo(
    () => comprobantes.filter((comprobante) => comprobante.estado === "EN_REVISION" || comprobante.estado === "OBSERVADO"),
    [comprobantes],
  );
  const presupuestoActual = presupuesto;
  const alicuotasValidas = distribucionValida(
    departamentos.map((departamento) => departamento.coeficiente),
  );
  const navActual = JUNTA_NAV_ITEMS.find((item) => item.id === section);

  const manejarPresupuestoAprobado = useCallback((nuevoPresupuesto: PresupuestoAprobado | null) => {
    setPresupuesto(nuevoPresupuesto);
    setFeedback(null);
  }, []);

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
      confirmacion.decision !== "APROBADO" &&
      !motivo.trim()
    ) {
      setFeedback("Indica el motivo para observar o rechazar el comprobante.");
      return;
    }

    setBusy(true);
    try {
      if (confirmacion.kind === "emitir" && presupuestoActual) {
        const resultado = await emitirLoteCuotas(
          presupuestoActual.periodo,
          presupuestoActual.condominioId,
        );
        setFeedback(resultado.ok
          ? `Emisión de ${presupuestoActual.periodo} completada para ${resultado.total} departamentos.`
          : `No se pudo emitir: ${resultado.error}`);
      } else if (confirmacion.kind === "comprobante") {
        const resultado = await conciliarComprobante(
          confirmacion.id,
          confirmacion.decision,
          confirmacion.decision !== "APROBADO" ? motivo.trim() : undefined,
        );
        if (resultado.ok) {
          setFeedback("La conciliación del comprobante se actualizó correctamente.");
          await loadData();
        } else {
          setFeedback(resultado.error || "No se pudo procesar el comprobante.");
        }
      } else if (confirmacion.kind === "comunicado" && condominioActivoId) {
        const resultado = await enviarComunicadoMasivo(titulo, mensaje, condominioActivoId, {
          canal: canalComunicado,
        });
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
          setFeedback(resultado.error || "No se pudo enviar el comunicado.");
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
        description={`${condominioActivoId ? "Condominio seleccionado" : "Sin condominio seleccionado"} · ${seccionTitulo}`}
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
              isAuditor={isAuditor}
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
              departamentos={departamentosRegistrados.length}
              comprobantesPendientes={pendientes.length}
              presupuesto={presupuesto}
              onNavigate={setSection}
            />
          )}
          {section === "configuracion" && isSuperAdmin && (
            <ConfiguracionCondominio
              puedeEditar={isSuperAdmin}
              condominioActivoId={condominioActivoId}
              onCondominioSeleccionado={seleccionarCondominio}
            />
          )}
          {section === "estructura" && (
            <EstructuraCondominio
              key={condominioActivoId ?? "sin-condominio"}
              condominioId={condominioActivoId}
              departamentos={departamentosRegistrados}
              soloLectura={isAuditor}
              cargando={loading}
              onActualizar={loadData}
            />
          )}
          {section === "usuarios" && !isAuditor && (
            <UsuariosSection key={condominioActivoId ?? "sin-condominio"} condominioId={condominioActivoId} esSuperAdmin={isSuperAdmin} usuarioActualId={user?.id ?? ""} />
          )}
          {section === "areas" && (
            <AreasSection key={condominioActivoId ?? "sin-condominio"} condominioId={condominioActivoId} soloLectura={isAuditor} />
          )}
          {section === "presupuesto" && (
            <>
              <AsistenteEmision
                paso={presupuesto ? 2 : 1}
                presupuestoAprobado={presupuesto !== null}
                distribucionAprobada={alicuotasValidas}
              />
              <PresupuestoMensual
                condominioId={condominioActivoId}
                puedeEditar={user?.rol === "ADMIN_JUNTA" || user?.rol === "SUPERADMIN"}
                onCambioAprobado={manejarPresupuestoAprobado}
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
              canal={canalComunicado}
              condominioId={condominioActivoId}
              departamentos={departamentos}
              error={loadError}
              onTituloChange={setTitulo}
              onMensajeChange={setMensaje}
              onCanalChange={setCanalComunicado}
              onSubmit={solicitarComunicado}
              onRetry={() => void loadData()}
              onRefresh={() => loadData()}
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
            {confirmacion.decision !== "APROBADO" && (
              <Field label="Motivo de la observación o rechazo" required>
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
  return confirmacion.decision === "APROBADO" ? "Aprobar comprobante" : confirmacion.decision === "OBSERVADO" ? "Observar comprobante" : "Rechazar comprobante";
}

function etiquetaConfirmacion(confirmacion: Confirmacion | null) {
  if (!confirmacion) return "Confirmar";
  if (confirmacion.kind === "emitir") return "Emitir cuotas";
  if (confirmacion.kind === "comunicado") return "Enviar comunicado";
  return confirmacion.decision === "APROBADO" ? "Aprobar comprobante" : confirmacion.decision === "OBSERVADO" ? "Observar comprobante" : "Rechazar comprobante";
}
