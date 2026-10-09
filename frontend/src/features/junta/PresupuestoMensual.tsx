"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { CalendarDays, CheckCircle2, ClipboardCheck, Info, Save } from "lucide-react";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { Field, Input, Select } from "@/components/ui/Field";
import { MoneyInput } from "@/components/ui/MoneyInput";
import { formatPeriodo } from "@/lib/format";
import type {
  DatosPresupuestoPayload,
  Moneda,
  PresupuestoMensual as PresupuestoPersistido,
} from "@/lib/api";
import {
  actualizarPresupuesto,
  aprobarPresupuesto,
  crearPresupuesto,
  obtenerPresupuestoPorPeriodo,
} from "@/lib/api";

export interface PresupuestoAprobado {
  id: string;
  condominioId: string;
  periodo: string;
  moneda: Moneda;
  montoTotal: string;
  fechaVencimiento: string;
  estado: "APROBADO";
}

type EstadoVista = "SIN_REGISTRAR" | "BORRADOR" | "APROBADO";

interface PresupuestoMensualProps {
  condominioId: string | null;
  puedeEditar: boolean;
  onCambioAprobado: (presupuesto: PresupuestoAprobado | null) => void;
}

function periodoActual(): string {
  return new Date().toISOString().slice(0, 7);
}

function comoPresupuestoAprobado(presupuesto: PresupuestoPersistido): PresupuestoAprobado | null {
  if (presupuesto.estado !== "APROBADO") return null;
  return {
    id: presupuesto.id,
    condominioId: presupuesto.condominio_id,
    periodo: presupuesto.periodo,
    moneda: presupuesto.moneda,
    montoTotal: presupuesto.monto_total,
    fechaVencimiento: presupuesto.fecha_vencimiento,
    estado: "APROBADO",
  };
}

export function PresupuestoMensual({
  condominioId,
  puedeEditar,
  onCambioAprobado,
}: PresupuestoMensualProps) {
  const periodoInicial = periodoActual();
  const [presupuestoId, setPresupuestoId] = useState<string | null>(null);
  const [periodo, setPeriodo] = useState(periodoInicial);
  const [moneda, setMoneda] = useState<Moneda>("PEN");
  const [montoTotal, setMontoTotal] = useState("");
  const [fechaVencimiento, setFechaVencimiento] = useState(`${periodoInicial}-20`);
  const [estado, setEstado] = useState<EstadoVista>("SIN_REGISTRAR");
  const [aprobadoPor, setAprobadoPor] = useState<string | null>(null);
  const [aprobadoEn, setAprobadoEn] = useState<string | null>(null);
  const [consultando, setConsultando] = useState(false);
  const [guardando, setGuardando] = useState(false);
  const [aprobando, setAprobando] = useState(false);
  const [cambiosPendientes, setCambiosPendientes] = useState(false);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmarAprobacion, setConfirmarAprobacion] = useState(false);

  const bloqueado = estado === "APROBADO" || !puedeEditar;

  const aplicarPresupuesto = useCallback((presupuesto: PresupuestoPersistido) => {
    setPresupuestoId(presupuesto.id);
    setPeriodo(presupuesto.periodo);
    setMoneda(presupuesto.moneda);
    setMontoTotal(presupuesto.monto_total);
    setFechaVencimiento(presupuesto.fecha_vencimiento);
    setEstado(presupuesto.estado);
    setAprobadoPor(presupuesto.aprobado_por);
    setAprobadoEn(presupuesto.aprobado_en);
    setCambiosPendientes(false);
    onCambioAprobado(comoPresupuestoAprobado(presupuesto));
  }, [onCambioAprobado]);

  const limpiarPeriodoSeleccionado = useCallback((periodoSeleccionado: string) => {
    setPresupuestoId(null);
    setMontoTotal("");
    setFechaVencimiento(`${periodoSeleccionado}-20`);
    setEstado("SIN_REGISTRAR");
    setAprobadoPor(null);
    setAprobadoEn(null);
    setCambiosPendientes(false);
    onCambioAprobado(null);
  }, [onCambioAprobado]);

  useEffect(() => {
    let cancelado = false;

    async function consultar() {
      setError(null);
      setMensaje(null);
      if (!condominioId) {
        setConsultando(false);
        limpiarPeriodoSeleccionado(periodo);
        setError("No hay un condominio activo. Seleccione uno antes de registrar presupuestos.");
        return;
      }

      setConsultando(true);
      const resultado = await obtenerPresupuestoPorPeriodo(condominioId, periodo);
      if (cancelado) return;
      setConsultando(false);

      if (!resultado.ok) {
        limpiarPeriodoSeleccionado(periodo);
        setError(resultado.error || "No se pudo consultar el presupuesto del periodo.");
        return;
      }
      if (resultado.notFound || !resultado.data) {
        limpiarPeriodoSeleccionado(periodo);
        setMensaje("Todavía no existe un presupuesto persistido para este periodo.");
        return;
      }
      aplicarPresupuesto(resultado.data);
      setMensaje(
        resultado.data.estado === "APROBADO"
          ? "Presupuesto aprobado recuperado desde PostgreSQL."
          : "Borrador recuperado desde PostgreSQL.",
      );
    }

    void consultar();
    return () => {
      cancelado = true;
    };
  }, [aplicarPresupuesto, condominioId, limpiarPeriodoSeleccionado, periodo]);

  function construirDatos(): DatosPresupuestoPayload | null {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(periodo)) {
      setError("El periodo debe utilizar el formato AAAA-MM.");
      return null;
    }
    const monto = Number(montoTotal);
    if (!Number.isFinite(monto) || monto <= 0 || monto > 9999999999.99) {
      setError("El monto total debe ser mayor que cero y respetar NUMERIC(12,2).");
      return null;
    }
    if (!fechaVencimiento || !fechaVencimiento.startsWith(`${periodo}-`)) {
      setError("La fecha de vencimiento debe pertenecer al periodo seleccionado.");
      return null;
    }

    const montoNormalizado = monto.toFixed(2);
    setMontoTotal(montoNormalizado);
    return {
      periodo,
      moneda,
      monto_total: montoNormalizado,
      fecha_vencimiento: fechaVencimiento,
    };
  }

  async function guardarBorrador() {
    setError(null);
    setMensaje(null);
    if (!puedeEditar || estado === "APROBADO") {
      setError("El presupuesto no puede modificarse con el rol o estado actual.");
      return;
    }
    if (!condominioId) {
      setError("No hay un condominio activo para guardar el presupuesto.");
      return;
    }
    const datos = construirDatos();
    if (!datos) return;

    setGuardando(true);
    try {
      const resultado = presupuestoId
        ? await actualizarPresupuesto(presupuestoId, datos)
        : await crearPresupuesto({ condominio_id: condominioId, ...datos });
      if (!resultado.ok || !resultado.data) {
        setError(resultado.error || "No se pudo guardar el presupuesto.");
        return;
      }
      aplicarPresupuesto(resultado.data);
      setMensaje(
        presupuestoId
          ? "Borrador actualizado y persistido correctamente."
          : `Borrador persistido con UUID ${resultado.data.id}.`,
      );
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "No se pudo guardar el presupuesto.");
    } finally {
      setGuardando(false);
    }
  }

  function solicitarAprobacion(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMensaje(null);
    if (!puedeEditar) {
      setError("Su rol no puede aprobar presupuestos.");
      return;
    }
    if (!presupuestoId) {
      setError("Primero guarde el borrador para obtener su UUID persistente.");
      return;
    }
    if (cambiosPendientes) {
      setError("Guarde los cambios pendientes antes de aprobar el presupuesto.");
      return;
    }
    setConfirmarAprobacion(true);
  }

  async function confirmarYaprobar() {
    if (!presupuestoId) return;
    setAprobando(true);
    try {
      const resultado = await aprobarPresupuesto(presupuestoId);
      if (!resultado.ok || !resultado.data) {
        setError(resultado.error || "No se pudo aprobar el presupuesto.");
        return;
      }
      aplicarPresupuesto(resultado.data);
      setMensaje("Presupuesto aprobado y auditado correctamente.");
      setConfirmarAprobacion(false);
    } catch (approveError) {
      setError(approveError instanceof Error ? approveError.message : "No se pudo aprobar el presupuesto.");
    } finally {
      setAprobando(false);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(17rem,0.85fr)]">
      <Card>
        <CardHeader
          title="Registrar presupuesto mensual"
          description="El presupuesto debe aprobarse antes de emitir las cuotas del periodo."
          icon={<ClipboardCheck className="h-5 w-5" aria-hidden="true" />}
          actions={<Badge tone={estado === "APROBADO" ? "success" : estado === "BORRADOR" ? "warning" : "neutral"}>{estado.replace("_", " ")}</Badge>}
        />
        <CardBody>
          <div className="space-y-3">
            {consultando && <Alert tone="info" title="Consultando presupuesto">Buscando el registro persistido del periodo.</Alert>}
            {error && <Alert tone="danger" title="Revisa los datos">{error}</Alert>}
            {mensaje && <Alert tone="success" title="Estado del presupuesto">{mensaje}</Alert>}
            {cambiosPendientes && presupuestoId && (
              <Alert tone="warning" title="Cambios pendientes">Guarda el borrador antes de aprobarlo.</Alert>
            )}
            {!puedeEditar && (
              <div className="rounded-lg border border-audit-200 bg-audit-50 p-3">
                <Badge tone="audit">Solo lectura</Badge>
                <p className="mt-2 text-sm text-audit-800">Puedes consultar periodos, pero no modificar ni aprobar presupuestos.</p>
              </div>
            )}
          </div>

          <form onSubmit={solicitarAprobacion} className="mt-5 space-y-5">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Condominio activo">
                <Input value={condominioId || "Sin contexto configurado"} readOnly />
              </Field>
              <Field label="Periodo" required>
                <Input type="month" value={periodo} onChange={(event) => setPeriodo(event.target.value)} disabled={consultando} />
              </Field>
              <Field label="Moneda" required>
                <Select
                  value={moneda}
                  onChange={(event) => {
                    setMoneda(event.target.value as Moneda);
                    setCambiosPendientes(true);
                  }}
                  disabled={bloqueado || consultando}
                >
                  <option value="PEN">PEN — Sol peruano</option>
                  <option value="USD">USD — Dólar estadounidense</option>
                </Select>
              </Field>
              <Field label="Monto total" required>
                <MoneyInput
                  value={montoTotal}
                  onValueChange={(value) => {
                    setMontoTotal(value);
                    setCambiosPendientes(true);
                  }}
                  moneda={moneda}
                  disabled={bloqueado || consultando}
                />
              </Field>
            </div>

            <Field label="Fecha de vencimiento" required className="md:w-1/2">
              <Input
                type="date"
                value={fechaVencimiento}
                onChange={(event) => {
                  setFechaVencimiento(event.target.value);
                  setCambiosPendientes(true);
                }}
                disabled={bloqueado || consultando}
              />
            </Field>

            {puedeEditar && (
              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void guardarBorrador()}
                  disabled={aprobando || consultando || estado === "APROBADO"}
                  loading={guardando}
                  loadingText="Guardando..."
                  icon={<Save className="h-4 w-4" aria-hidden="true" />}
                >
                  Guardar borrador
                </Button>
                <Button
                  type="submit"
                  disabled={!presupuestoId || cambiosPendientes || guardando || estado === "APROBADO"}
                  icon={<CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
                >
                  Aprobar presupuesto
                </Button>
              </div>
            )}
          </form>
        </CardBody>
      </Card>

      <aside className="space-y-4">
        <Card>
          <CardHeader title="Estado del periodo" />
          <CardBody className="space-y-4">
            <div className="flex items-center gap-3">
              <CalendarDays className="h-6 w-6 text-info-600" aria-hidden="true" />
              <div>
                <p className="font-semibold">{formatPeriodo(periodo)}</p>
                <p className="text-sm text-muted">Estado: {estado.replace("_", " ")}</p>
              </div>
            </div>
            <div className="rounded-lg bg-canvas p-4 text-sm">
              <p>Monto: {montoTotal ? <MoneyAmount value={montoTotal} moneda={moneda} /> : "Sin registrar"}</p>
              <p className="mt-1">Vencimiento: {fechaVencimiento || "Sin definir"}</p>
              {presupuestoId && <p className="mt-1 break-all font-mono text-xs">UUID: {presupuestoId}</p>}
              {aprobadoPor && <p className="mt-1">Aprobado por: {aprobadoPor}</p>}
              {aprobadoEn && <p className="mt-1">Aprobado en: {new Date(aprobadoEn).toLocaleString("es-PE")}</p>}
            </div>
          </CardBody>
        </Card>
        <Alert tone="info" title="Persistencia del presupuesto">
          <span className="inline-flex items-start gap-2">
            <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            Los borradores y aprobaciones se guardan en PostgreSQL. Una vez aprobado, el presupuesto queda bloqueado.
          </span>
        </Alert>
      </aside>

      <ConfirmDialog
        open={confirmarAprobacion}
        title="Aprobar presupuesto"
        confirmLabel="Aprobar presupuesto"
        loading={aprobando}
        onCancel={() => setConfirmarAprobacion(false)}
        onConfirm={() => void confirmarYaprobar()}
      >
        <p>
          Se aprobará el presupuesto de {formatPeriodo(periodo)} por{" "}
          {montoTotal && <MoneyAmount value={montoTotal} moneda={moneda} />}.
        </p>
        <p>Después de aprobarlo no podrá editarse y quedará disponible para emitir cuotas.</p>
      </ConfirmDialog>
    </div>
  );
}

export default PresupuestoMensual;
