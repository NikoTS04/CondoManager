"use client";

import { FormEvent, useState } from "react";
import { CalendarDays, CheckCircle2, ClipboardCheck, Info, Save } from "lucide-react";

export type PresupuestoAprobado = {
  condominioId: string;
  periodo: string;
  moneda: "PEN" | "USD";
  montoTotal: string;
  fechaVencimiento: string;
  estado: "APROBADO";
};

type PresupuestoMensualProps = {
  condominioId: string;
  puedeEditar: boolean;
  onAprobar: (presupuesto: PresupuestoAprobado) => void;
};

export default function PresupuestoMensual({ condominioId, puedeEditar, onAprobar }: PresupuestoMensualProps) {
  const [periodo, setPeriodo] = useState("2026-11");
  const [moneda, setMoneda] = useState<"PEN" | "USD">("PEN");
  const [montoTotal, setMontoTotal] = useState("20850.00");
  const [fechaVencimiento, setFechaVencimiento] = useState("2026-11-20");
  const [estado, setEstado] = useState<"SIN_REGISTRAR" | "BORRADOR" | "APROBADO">("SIN_REGISTRAR");
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  function construirPresupuesto(): PresupuestoAprobado | null {
    const monto = Number(montoTotal);
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(periodo)) {
      setError("El periodo debe utilizar el formato AAAA-MM.");
      return null;
    }
    if (!Number.isFinite(monto) || monto <= 0) {
      setError("El monto total del presupuesto debe ser mayor que cero.");
      return null;
    }
    if (!fechaVencimiento || !fechaVencimiento.startsWith(periodo)) {
      setError("La fecha de vencimiento debe pertenecer al periodo seleccionado.");
      return null;
    }
    return {
      condominioId,
      periodo,
      moneda,
      montoTotal: monto.toFixed(2),
      fechaVencimiento,
      estado: "APROBADO",
    };
  }

  function guardarBorrador() {
    setError(null);
    setMensaje(null);
    if (!puedeEditar) {
      setError("Su rol no puede modificar presupuestos.");
      return;
    }
    if (!construirPresupuesto()) return;
    setEstado("BORRADOR");
    setMensaje("Borrador validado localmente. Todavía no habilita la emisión de cuotas.");
  }

  function aprobarPresupuesto(evento: FormEvent) {
    evento.preventDefault();
    setError(null);
    setMensaje(null);
    if (!puedeEditar) {
      setError("Su rol no puede aprobar presupuestos.");
      return;
    }
    const presupuesto = construirPresupuesto();
    if (!presupuesto) return;
    setEstado("APROBADO");
    setMensaje("Presupuesto aprobado en el prototipo. La emisión mensual quedó habilitada.");
    onAprobar(presupuesto);
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1.35fr_0.85fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">Gestión financiera</p>
            <h2 className="mt-1 flex items-center gap-2 text-xl font-bold text-slate-900">
              <ClipboardCheck className="h-5 w-5 text-blue-600" /> Registrar presupuesto mensual
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              El presupuesto debe aprobarse antes de ejecutar la emisión ordinaria del periodo.
            </p>
          </div>
          <span className="rounded-full bg-amber-100 px-3 py-1 text-[10px] font-bold text-amber-800">
            PROTOTIPO FRONTEND
          </span>
        </div>

        <form onSubmit={aprobarPresupuesto} className="mt-5 space-y-5">
          {error && <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">{error}</div>}
          {mensaje && <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-xs text-emerald-800">{mensaje}</div>}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-xs font-semibold text-slate-700">
              Condominio
              <input
                value="Villa Bonita 3"
                disabled
                className="mt-1.5 w-full rounded-lg border border-slate-300 bg-slate-100 px-3 py-2.5 text-sm font-normal text-slate-500"
              />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Periodo
              <input
                type="month"
                value={periodo}
                onChange={(evento) => {
                  setPeriodo(evento.target.value);
                  setFechaVencimiento(`${evento.target.value}-20`);
                }}
                disabled={!puedeEditar}
                className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal disabled:bg-slate-100"
                required
              />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Moneda
              <select
                value={moneda}
                onChange={(evento) => setMoneda(evento.target.value as "PEN" | "USD")}
                disabled={!puedeEditar}
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
                step="0.01"
                value={montoTotal}
                onChange={(evento) => setMontoTotal(evento.target.value)}
                disabled={!puedeEditar}
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
              onChange={(evento) => setFechaVencimiento(evento.target.value)}
              disabled={!puedeEditar}
              className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal disabled:bg-slate-100 md:w-1/2"
              required
            />
          </label>

          {puedeEditar ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={guardarBorrador}
                className="flex items-center justify-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50"
              >
                <Save className="h-4 w-4" /> Guardar borrador
              </button>
              <button className="flex items-center justify-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-xs font-bold text-white hover:bg-emerald-700">
                <CheckCircle2 className="h-4 w-4" /> Aprobar presupuesto
              </button>
            </div>
          ) : (
            <div className="rounded-xl border border-purple-200 bg-purple-50 p-3 text-center text-xs font-semibold text-purple-800">
              Modo auditor: puede revisar el presupuesto, pero no modificarlo ni aprobarlo.
            </div>
          )}
        </form>
      </section>

      <aside className="space-y-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Estado del periodo</p>
          <div className="mt-4 flex items-center gap-3">
            <div className={`flex h-11 w-11 items-center justify-center rounded-xl ${estado === "APROBADO" ? "bg-emerald-100 text-emerald-700" : estado === "BORRADOR" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-500"}`}>
              <CalendarDays className="h-6 w-6" />
            </div>
            <div>
              <p className="font-bold text-slate-900">Periodo {periodo}</p>
              <p className="text-xs text-slate-500">Estado: {estado.replace("_", " ")}</p>
            </div>
          </div>
          <div className="mt-4 rounded-xl bg-slate-50 p-4 text-xs text-slate-600">
            <p>Monto: {moneda} {Number(montoTotal || 0).toFixed(2)}</p>
            <p className="mt-1">Vencimiento: {fechaVencimiento || "Sin definir"}</p>
          </div>
        </div>

        <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5 text-blue-950">
          <div className="flex items-start gap-3">
            <Info className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
            <p className="text-xs leading-relaxed text-blue-800">
              Al conectar el backend, el botón de aprobación deberá guardar el presupuesto, registrar al actor y retornar un identificador persistente. Por ahora solo habilita la demostración frontend.
            </p>
          </div>
        </div>
      </aside>
    </div>
  );
}
