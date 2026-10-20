"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import RoleGuard from "@/components/RoleGuard";
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
  const dptoParam = searchParams.get("dpto");
  const { user, activeDepartment, setActiveDepartment } = useAuth();

  const [departamentoNumero, setDepartamentoNumero] = useState(
    dptoParam || activeDepartment || "102",
  );
  const [departamentos, setDepartamentos] = useState<Departamento[]>([]);
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

    const [deptosRes, areasRes, reservasRes, compsRes] = await Promise.allSettled([
      fetchDepartamentos(),
      fetchAreasComunes(),
      fetchReservas(),
      fetchComprobantes(),
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
  }, []);

  const reloadReservas = useCallback(async () => {
    setLoadingReservas(true);
    setErrorReservas(null);
    try {
      const data = await fetchReservas();
      setReservas(data);
    } catch {
      setErrorReservas("No pudimos actualizar las reservas.");
    } finally {
      setLoadingReservas(false);
    }
  }, []);

  const reloadComprobantes = useCallback(async () => {
    setLoadingComprobantes(true);
    setErrorComprobantes(null);
    try {
      const data = await fetchComprobantes();
      setComprobantes(data);
    } catch {
      setErrorComprobantes("No pudimos actualizar los comprobantes.");
    } finally {
      setLoadingComprobantes(false);
    }
  }, []);

  const reloadAreas = useCallback(async () => {
    setLoadingAreas(true);
    setErrorAreas(null);
    try {
      const data = await fetchAreasComunes();
      setAreas(data);
    } catch {
      setErrorAreas("No pudimos actualizar los espacios comunes.");
    } finally {
      setLoadingAreas(false);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    void loadData(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, [loadData]);

  useEffect(() => {
    if (dptoParam) {
      setDepartamentoNumero(dptoParam);
      setActiveDepartment(dptoParam);
    }
  }, [dptoParam, setActiveDepartment]);

  // Si los departamentos cargaron y el número actual no existe en ellos, sincroniza con el primero
  useEffect(() => {
    if (
      departamentos.length > 0 &&
      !departamentos.some((d) => d.numero === departamentoNumero)
    ) {
      const defaultNumero = departamentos[0].numero;
      setDepartamentoNumero(defaultNumero);
      setActiveDepartment(defaultNumero);
    }
  }, [departamentos, departamentoNumero, setActiveDepartment]);

  function handleSelectDepartamento(num: string) {
    setDepartamentoNumero(num);
    setActiveDepartment(num);
  }

  const deptoActual =
    departamentos.find((d) => d.numero === departamentoNumero) ?? null;

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
              areas={areas}
              condominioId={user?.condominio_id}
              departamentoNumero={departamentoNumero}
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
              reservas={reservas}
              areas={areas}
              departamentoNumero={departamentoNumero}
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
              departamentoNumero={departamentoNumero}
              onSuccess={reloadComprobantes}
              comprobantesExistentes={comprobantes}
            />
          </div>
          <div className="lg:col-span-2">
            <ComprobantesList
              comprobantes={comprobantes}
              departamentoNumero={departamentoNumero}
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
    <RoleGuard allowedRoles={["PROPIETARIO", "INQUILINO", "ADMIN_JUNTA", "SUPERADMIN"]}>
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
