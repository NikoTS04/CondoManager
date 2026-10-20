"use client";

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import RoleGuard from "@/components/RoleGuard";
import { seleccionarUnidad } from "@/lib/session";
import {
  type AreaComun,
  type Departamento,
  type Reserva,
  type ComprobantePago,
  fetchAreasComunes,
  fetchDepartamentos,
  fetchReservas,
  fetchComprobantes,
} from "@/lib/api";
import { SolvenciaBanner } from "@/components/domain/SolvenciaBanner";
import { Spinner } from "@/components/ui/Feedback";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import {
  ResidenteNav,
  type ResidenteTab,
  ResidenteHeader,
  ResumenCuenta,
  ReportarPagoForm,
  ComprobantesList,
  ReservarAreaForm,
  MisReservasList,
} from "@/features/residente";

function ResidenteContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const dptoParam = searchParams.get("dpto");
  const { user, activeDepartment, setActiveDepartment } = useAuth();

  const [departamentosRecibidos, setDepartamentos] = useState<Departamento[]>([]);
  const departamentos = useMemo(() => departamentosRecibidos.filter((d) => d.activo !== false &&
    (user?.rol !== "RESIDENTE" || user.departamentos.some((v) => v.es_activo && v.departamento_id === d.id))),
    [departamentosRecibidos, user]);
  const departamentoId = user ? seleccionarUnidad(user, dptoParam, activeDepartment, departamentos.map((d) => d.id)) : "";
  const [contextoId] = useState(() => user?.condominio_id ||
    (user?.rol === "SUPERADMIN" ? localStorage.getItem("condo_active_id") : null));
  const [activeTab, setActiveTab] = useState<ResidenteTab>("reservas");

  const [areas, setAreas] = useState<AreaComun[]>([]);
  const [reservas, setReservas] = useState<Reserva[]>([]);
  const [comprobantes, setComprobantes] = useState<ComprobantePago[]>([]);

  // Estados de carga y error por recurso independiente
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [loadingReservas, setLoadingReservas] = useState(false);
  const [loadingComprobantes, setLoadingComprobantes] = useState(false);
  const [loadingAreas, setLoadingAreas] = useState(false);

  const [errorDeptos, setErrorDeptos] = useState<string | null>(null);
  const [errorAreas, setErrorAreas] = useState<string | null>(null);
  const [errorReservas, setErrorReservas] = useState<string | null>(null);
  const [errorComprobantes, setErrorComprobantes] = useState<string | null>(null);

  const loadData = useCallback(async (isCancelled?: () => boolean) => {
    setLoadingInitial(true);
    setErrorDeptos(null);
    setErrorAreas(null);
    setErrorReservas(null);
    setErrorComprobantes(null);
    setDepartamentos([]);
    setAreas([]);
    setReservas([]);
    setComprobantes([]);
    if (!contextoId) {
      setErrorDeptos("Selecciona primero un condominio en el portal de Junta.");
      setLoadingInitial(false);
      return;
    }

    const [deptosRes, areasRes, reservasRes, compsRes] = await Promise.allSettled([
      fetchDepartamentos(contextoId),
      fetchAreasComunes(contextoId),
      fetchReservas(undefined, undefined, contextoId),
      fetchComprobantes(contextoId),
    ]);

    if (isCancelled && isCancelled()) return;

    if (deptosRes.status === "fulfilled") {
      setDepartamentos(deptosRes.value);
    } else {
      setErrorDeptos("No pudimos cargar los datos de los departamentos.");
    }

    if (areasRes.status === "fulfilled") {
      setAreas(areasRes.value);
    } else {
      setErrorAreas("No pudimos cargar los espacios comunes.");
    }

    if (reservasRes.status === "fulfilled") {
      setReservas(reservasRes.value);
    } else {
      setErrorReservas("No pudimos cargar las reservas.");
    }

    if (compsRes.status === "fulfilled") {
      setComprobantes(compsRes.value);
    } else {
      setErrorComprobantes("No pudimos cargar los comprobantes.");
    }

    setLoadingInitial(false);
  }, [contextoId]);

  const reloadReservas = useCallback(async () => {
    setLoadingReservas(true);
    setErrorReservas(null);
    try {
      const data = await fetchReservas(undefined, undefined, contextoId);
      setReservas(data);
    } catch {
      setErrorReservas("No pudimos actualizar las reservas.");
    } finally {
      setLoadingReservas(false);
    }
  }, [contextoId]);

  const reloadComprobantes = useCallback(async () => {
    setLoadingComprobantes(true);
    setErrorComprobantes(null);
    try {
      const data = await fetchComprobantes(contextoId);
      setComprobantes(data);
    } catch {
      setErrorComprobantes("No pudimos actualizar los comprobantes.");
    } finally {
      setLoadingComprobantes(false);
    }
  }, [contextoId]);

  const reloadAreas = useCallback(async () => {
    setLoadingAreas(true);
    setErrorAreas(null);
    try {
      const data = await fetchAreasComunes(contextoId);
      setAreas(data);
    } catch {
      setErrorAreas("No pudimos actualizar los espacios comunes.");
    } finally {
      setLoadingAreas(false);
    }
  }, [contextoId]);

  useEffect(() => {
    let cancelled = false;
    void loadData(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadData]);

  useEffect(() => {
    if (departamentoId) {
      if (departamentoId !== activeDepartment) setActiveDepartment(departamentoId);
      if (dptoParam && dptoParam !== departamentoId) router.replace(`/residente?dpto=${departamentoId}`);
    }
  }, [departamentoId, activeDepartment, dptoParam, setActiveDepartment, router]);

  function handleSelectDepartamento(id: string) {
    if (!user || seleccionarUnidad(user, id, null, departamentos.map((d) => d.id)) !== id) return;
    router.replace(`/residente?dpto=${id}`);
  }

  const deptoActual =
    departamentos.find((d) => d.id === departamentoId) ?? null;

  const estaEnMora = deptoActual?.estado_financiero === "EN_MORA";

  return (
    <div className="space-y-6 pb-24 sm:pb-8">
      {/* Encabezado con selector de departamento */}
      <ResidenteHeader
        depto={deptoActual}
        departamentos={departamentos}
        onSelectDepartamento={handleSelectDepartamento}
        user={user}
      />

      {/* Error de departamentos si falló la carga */}
      {errorDeptos && (
        <Alert
          tone="danger"
          title="No pudimos cargar la información de tu departamento"
          action={
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void loadData()}
            >
              Reintentar
            </Button>
          }
        >
          {errorDeptos}
        </Alert>
      )}

      {/* Solo mostrar SolvenciaBanner si el departamento está confirmado por backend */}
      {deptoActual && !loadingInitial && !errorDeptos && (
        <SolvenciaBanner
          solvente={deptoActual.estado_financiero === "AL_DIA"}
          deudaVencida={deptoActual.deuda_vencida}
          onReportarPago={() => setActiveTab("pagos")}
        />
      )}

      {/* Navegación responsiva: Tabs en sm+ y barra inferior fija en móvil */}
      <ResidenteNav activeTab={activeTab} onChangeTab={setActiveTab} />

      {/* Contenido según la pestaña activa */}
      {activeTab === "reservas" && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <ReservarAreaForm
              key={departamentoId}
              areas={areas}
              condominioId={contextoId}
              departamentoId={departamentoId}
              estaEnMora={estaEnMora}
              deudaVencida={deptoActual?.deuda_vencida}
              errorAreas={errorAreas}
              onRetryAreas={reloadAreas}
              onSuccess={reloadReservas}
              onGoToPagos={() => setActiveTab("pagos")}
            />
          </div>
          <div className="lg:col-span-2">
            <MisReservasList
              reservas={reservas.filter((r) => r.departamento_id === departamentoId)}
              areas={areas}
              departamentoId={departamentoId}
              loading={loadingInitial || loadingReservas || loadingAreas}
              error={errorReservas}
              errorAreas={errorAreas}
              onRetry={reloadReservas}
              onRetryAreas={reloadAreas}
              onReservaCancelled={reloadReservas}
            />
          </div>
        </div>
      )}

      {activeTab === "pagos" && (
        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <ReportarPagoForm
              key={departamentoId}
              departamentoId={departamentoId}
              onSuccess={reloadComprobantes}
              comprobantesExistentes={comprobantes}
            />
          </div>
          <div className="lg:col-span-2">
            <ComprobantesList
              comprobantes={comprobantes}
              departamentoId={departamentoId}
              loading={loadingInitial || loadingComprobantes}
              error={errorComprobantes}
              onRetry={reloadComprobantes}
            />
          </div>
        </div>
      )}

      {activeTab === "cuenta" && (
        <>
          {deptoActual ? (
            <ResumenCuenta
              depto={deptoActual}
              loading={loadingInitial}
              error={errorDeptos}
              onRetry={() => void loadData()}
            />
          ) : (
            <Alert
              tone="warning"
              title="Información de cuenta no disponible"
              action={
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void loadData()}
                >
                  Reintentar
                </Button>
              }
            >
              No se pudo asociar la cuenta de este departamento con los registros del condominio.
            </Alert>
          )}
        </>
      )}
    </div>
  );
}

export default function ResidentePage() {
  return (
    <RoleGuard allowedRoles={["RESIDENTE", "ADMIN_JUNTA", "SUPERADMIN"]}>
      <Suspense
        fallback={
          <div className="flex min-h-64 items-center justify-center p-8">
            <Spinner label="Cargando Portal de Residentes…" />
          </div>
        }
      >
        <ResidenteContent />
      </Suspense>
    </RoleGuard>
  );
}
