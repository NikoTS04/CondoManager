"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import {
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  Info,
  Loader2,
  Save,
} from "lucide-react";
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

export type PresupuestoAprobado = {
  id: string;
  condominioId: string;
  periodo: string;
  moneda: Moneda;
  montoTotal: string;
  fechaVencimiento: string;
  estado: "APROBADO";
};

type EstadoVista = "SIN_REGISTRAR" | "BORRADOR" | "APROBADO";

type PresupuestoMensualProps = {
  condominioId: string | null;
  puedeEditar: boolean;
  onCambioAprobado: (presupuesto: PresupuestoAprobado | null) => void;
};

function periodoActual(): string {
  return new Date().toISOString().slice(0, 7);
}

function comoPresupuestoAprobado(
  presupuesto: PresupuestoPersistido
): PresupuestoAprobado | null {
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

export default function PresupuestoMensual({
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
        setError(
          "No hay un condominio activo. Configure el UUID real del condominio antes de registrar presupuestos."
        );
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
          : "Borrador recuperado desde PostgreSQL."
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
    const resultado = presupuestoId
      ? await actualizarPresupuesto(presupuestoId, datos)
      : await crearPresupuesto({ condominio_id: condominioId, ...datos });
    setGuardando(false);

    if (!resultado.ok || !resultado.data) {
      setError(resultado.error || "No se pudo guardar el presupuesto.");
      return;
    }
    aplicarPresupuesto(resultado.data);
    setMensaje(
      presupuestoId
        ? "Borrador actualizado y persistido correctamente."
        : `Borrador persistido con UUID ${resultado.data.id}.`
    );
  }

  async function aprobar(evento: FormEvent) {
    evento.preventDefault();
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

    setAprobando(true);
    const resultado = await aprobarPresupuesto(presupuestoId);
    setAprobando(false);
    if (!resultado.ok || !resultado.data) {
      setError(resultado.error || "No se pudo aprobar el presupuesto.");
      return;
    }
    aplicarPresupuesto(resultado.data);
    setMensaje("Presupuesto aprobado y auditado correctamente.");
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1.35fr_0.85fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">
              Gestión financiera
            </p>
            <h2 className="mt-1 flex items-center gap-2 text-xl font-bold text-slate-900">
              <ClipboardCheck className="h-5 w-5 text-blue-600" /> Registrar presupuesto mensual
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              El presupuesto debe aprobarse antes de ejecutar la emisión ordinaria del periodo.
            </p>
          </div>
          <span
            className={`rounded-full px-3 py-1 text-[10px] font-bold ${
              estado === "APROBADO"
                ? "bg-emerald-100 text-emerald-800"
                : estado === "BORRADOR"
                  ? "bg-amber-100 text-amber-800"
                  : "bg-slate-100 text-slate-600"
            }`}
          >
            {estado.replace("_", " ")}
          </span>
        </div>

        <form onSubmit={aprobar} className="mt-5 space-y-5">
          {consultando && (
            <div className="flex items-center gap-2 rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs text-blue-800">
              <Loader2 className="h-4 w-4 animate-spin" /> Consultando el presupuesto persistido...
            </div>
          )}
          {error && (
            <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">
              {error}
            </div>
          )}
          {mensaje && (
            <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">
              {mensaje}
            </div>
          )}
          {cambiosPendientes && presupuestoId && (
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              Hay cambios pendientes. Guarde el borrador antes de aprobarlo.
            </div>
          )}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-xs font-semibold text-slate-700">
              Condominio activo
              <input
                value={condominioId || "Sin contexto configurado"}
                disabled
                className="mt-1.5 w-full rounded-lg border border-slate-300 bg-slate-100 px-3 py-2.5 text-sm font-normal text-slate-500"
              />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Periodo
              <input
                type="month"
                value={periodo}
                onChange={(evento) => setPeriodo(evento.target.value)}
                disabled={consultando}
                className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal disabled:bg-slate-100"
                required
              />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Moneda
              <select
                value={moneda}
                onChange={(evento) => {
                  setMoneda(evento.target.value as Moneda);
                  setCambiosPendientes(true);
                }}
                disabled={bloqueado || consultando}
                className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm font-normal disabled:bg-slate-100"
              >
                <option value="PEN">PEN — Sol peruano</option>
                <option value="USD">USD — Dólar estadounidense</option>
              </select>
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Monto total aprobado
              <input
                type="number"
                min="0.01"
                max="9999999999.99"
                step="0.01"
                value={montoTotal}
                onChange={(evento) => {
                  setMontoTotal(evento.target.value);
                  setCambiosPendientes(true);
                }}
                disabled={bloqueado || consultando}
                className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal disabled:bg-slate-100"
                required
              />
            </label>
          </div>

          <label className="block text-xs font-semibold text-slate-700">
            Fecha de vencimiento
            <input
              type="date"
              value={fechaVencimiento}
              onChange={(evento) => {
                setFechaVencimiento(evento.target.value);
                setCambiosPendientes(true);
              }}
              disabled={bloqueado || consultando}
              className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal disabled:bg-slate-100 md:w-1/2"
              required
            />
          </label>

          {puedeEditar ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={() => void guardarBorrador()}
                disabled={guardando || aprobando || consultando || estado === "APROBADO"}
                className="flex items-center justify-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:bg-slate-100 disabled:text-slate-400"
              >
                {guardando ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                {guardando ? "Guardando..." : "Guardar borrador"}
              </button>
              <button
                type="submit"
                disabled={
                  !presupuestoId ||
                  cambiosPendientes ||
                  guardando ||
                  aprobando ||
                  estado === "APROBADO"
                }
                className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300 disabled:text-slate-600"
              >
                {aprobando ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <CheckCircle2 className="h-4 w-4" />
                )}
                {aprobando ? "Aprobando..." : "Aprobar presupuesto"}
              </button>
            </div>
          ) : (
            <div className="rounded-xl border border-purple-200 bg-purple-50 p-3 text-center text-xs font-semibold text-purple-800">
              Modo auditor: puede seleccionar periodos y revisar presupuestos, pero no modificarlos.
            </div>
          )}
        </form>
      </section>

      <aside className="space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
            Estado del periodo
          </p>
          <div className="mt-4 flex items-center gap-3">
            <div
              className={`flex h-11 w-11 items-center justify-center rounded-xl ${
                estado === "APROBADO"
                  ? "bg-emerald-100 text-emerald-700"
                  : estado === "BORRADOR"
                    ? "bg-amber-100 text-amber-700"
                    : "bg-slate-100 text-slate-500"
              }`}
            >
              <CalendarDays className="h-6 w-6" />
            </div>
            <div>
              <p className="font-bold text-slate-900">Periodo {periodo}</p>
              <p className="text-xs text-slate-500">Estado: {estado.replace("_", " ")}</p>
            </div>
          </div>
          <div className="mt-4 rounded-xl bg-slate-50 p-4 text-xs text-slate-600">
            <p>
              Monto: {moneda} {montoTotal || "0.00"}
            </p>
            <p className="mt-1">Vencimiento: {fechaVencimiento || "Sin definir"}</p>
            {presupuestoId && <p className="mt-1 break-all">UUID: {presupuestoId}</p>}
            {aprobadoPor && <p className="mt-1">Aprobado por: {aprobadoPor}</p>}
            {aprobadoEn && (
              <p className="mt-1">
                Aprobado en: {new Date(aprobadoEn).toLocaleString("es-PE")}
              </p>
            )}
          </div>
        </div>

        <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5 text-blue-950">
          <div className="flex items-start gap-3">
            <Info className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
            <p className="text-xs leading-relaxed text-blue-800">
              Los borradores y aprobaciones se guardan en PostgreSQL. Una vez aprobado, el
              presupuesto queda bloqueado y disponible como fuente para la futura emisión de
              CON-11.
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
}
