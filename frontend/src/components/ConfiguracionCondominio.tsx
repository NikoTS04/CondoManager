"use client";

import { FormEvent, useState } from "react";
import { Building2, CheckCircle2, CircleDollarSign, Info, Save, Settings2 } from "lucide-react";

type Moneda = "PEN" | "USD";
type ReglaMora = "MONTO_FIJO" | "PORCENTAJE_SALDO";

type ConfiguracionGuardada = {
  nombre: string;
  direccion: string;
  moneda: Moneda;
  reglaMora: ReglaMora;
  montoMoraFijo: string;
  tasaMoraPorcentaje: string;
  diaCorte: number;
  diasGracia: number;
  activo: true;
};

export default function ConfiguracionCondominio({ puedeEditar }: { puedeEditar: boolean }) {
  const [nombre, setNombre] = useState("Villa Bonita 3");
  const [direccion, setDireccion] = useState("Av. Principal 123, Lima");
  const [moneda, setMoneda] = useState<Moneda>("PEN");
  const [reglaMora, setReglaMora] = useState<ReglaMora>("MONTO_FIJO");
  const [montoMoraFijo, setMontoMoraFijo] = useState("20.00");
  const [tasaMoraPorcentaje, setTasaMoraPorcentaje] = useState("0.0000");
  const [diaCorte, setDiaCorte] = useState("20");
  const [diasGracia, setDiasGracia] = useState("2");
  const [error, setError] = useState<string | null>(null);
  const [configuracion, setConfiguracion] = useState<ConfiguracionGuardada | null>(null);

  function guardarConfiguracion(evento: FormEvent) {
    evento.preventDefault();
    setError(null);

    if (!puedeEditar) {
      setError("Solo un usuario SuperAdmin puede configurar un condominio.");
      return;
    }

    const corte = Number(diaCorte);
    const gracia = Number(diasGracia);
    const moraFija = Number(montoMoraFijo);
    const tasa = Number(tasaMoraPorcentaje);

    if (!nombre.trim() || !direccion.trim()) {
      setError("El nombre y la dirección del condominio son obligatorios.");
      return;
    }
    if (!Number.isInteger(corte) || corte < 1 || corte > 28) {
      setError("El día de corte debe ser un número entero entre 1 y 28.");
      return;
    }
    if (!Number.isInteger(gracia) || gracia < 0) {
      setError("Los días de gracia deben ser un número entero mayor o igual que cero.");
      return;
    }
    if (reglaMora === "MONTO_FIJO" && (!Number.isFinite(moraFija) || moraFija < 0)) {
      setError("El monto fijo de mora debe ser un importe válido mayor o igual que cero.");
      return;
    }
    if (reglaMora === "PORCENTAJE_SALDO" && (!Number.isFinite(tasa) || tasa < 0 || tasa > 100)) {
      setError("La tasa de mora debe encontrarse entre 0 y 100 por ciento.");
      return;
    }

    setConfiguracion({
      nombre: nombre.trim(),
      direccion: direccion.trim(),
      moneda,
      reglaMora,
      montoMoraFijo: moraFija.toFixed(2),
      tasaMoraPorcentaje: tasa.toFixed(4),
      diaCorte: corte,
      diasGracia: gracia,
      activo: true,
    });
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[1.5fr_0.8fr]">
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex items-start justify-between gap-4 border-b border-slate-100 pb-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">Administración general</p>
            <h2 className="mt-1 flex items-center gap-2 text-xl font-bold text-slate-900">
              <Settings2 className="h-5 w-5 text-blue-600" /> Configurar un condominio
            </h2>
            <p className="mt-1 text-xs text-slate-500">
              Define la identidad, moneda y reglas financieras generales de la organización.
            </p>
          </div>
          <span className="rounded-full bg-amber-100 px-3 py-1 text-[10px] font-bold text-amber-800">
            PROTOTIPO FRONTEND
          </span>
        </div>

        <form onSubmit={guardarConfiguracion} className="mt-5 space-y-5">
          {error && <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-xs text-rose-800">{error}</div>}

          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-xs font-semibold text-slate-700">
              Nombre del condominio
              <input
                value={nombre}
                onChange={(evento) => setNombre(evento.target.value)}
                disabled={!puedeEditar}
                className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
                required
              />
            </label>
            <label className="text-xs font-semibold text-slate-700">
              Moneda principal
              <select
                value={moneda}
                onChange={(evento) => setMoneda(evento.target.value as Moneda)}
                disabled={!puedeEditar}
                className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm font-normal disabled:bg-slate-100"
              >
                <option value="PEN">PEN — Sol peruano</option>
                <option value="USD">USD — Dólar estadounidense</option>
              </select>
            </label>
          </div>

          <label className="block text-xs font-semibold text-slate-700">
            Dirección
            <textarea
              value={direccion}
              onChange={(evento) => setDireccion(evento.target.value)}
              disabled={!puedeEditar}
              rows={2}
              className="mt-1.5 w-full resize-none rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:bg-slate-100"
              required
            />
          </label>

          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <h3 className="flex items-center gap-2 text-sm font-bold text-slate-900">
              <CircleDollarSign className="h-4 w-4 text-amber-600" /> Reglas generales de cobranza
            </h3>
            <div className="mt-4 grid gap-4 md:grid-cols-2">
              <label className="text-xs font-semibold text-slate-700">
                Regla de mora
                <select
                  value={reglaMora}
                  onChange={(evento) => setReglaMora(evento.target.value as ReglaMora)}
                  disabled={!puedeEditar}
                  className="mt-1.5 w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm font-normal disabled:bg-slate-100"
                >
                  <option value="MONTO_FIJO">Monto fijo</option>
                  <option value="PORCENTAJE_SALDO">Porcentaje sobre saldo</option>
                </select>
              </label>

              {reglaMora === "MONTO_FIJO" ? (
                <label className="text-xs font-semibold text-slate-700">
                  Monto fijo de mora
                  <input
                    type="number"
                    min="0"
                    step="0.01"
                    value={montoMoraFijo}
                    onChange={(evento) => setMontoMoraFijo(evento.target.value)}
                    disabled={!puedeEditar}
                    className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal disabled:bg-slate-100"
                  />
                </label>
              ) : (
                <label className="text-xs font-semibold text-slate-700">
                  Tasa de mora (%)
                  <input
                    type="number"
                    min="0"
                    max="100"
                    step="0.0001"
                    value={tasaMoraPorcentaje}
                    onChange={(evento) => setTasaMoraPorcentaje(evento.target.value)}
                    disabled={!puedeEditar}
                    className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal disabled:bg-slate-100"
                  />
                </label>
              )}

              <label className="text-xs font-semibold text-slate-700">
                Día de corte mensual
                <input
                  type="number"
                  min="1"
                  max="28"
                  value={diaCorte}
                  onChange={(evento) => setDiaCorte(evento.target.value)}
                  disabled={!puedeEditar}
                  className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal disabled:bg-slate-100"
                />
              </label>
              <label className="text-xs font-semibold text-slate-700">
                Días de gracia
                <input
                  type="number"
                  min="0"
                  value={diasGracia}
                  onChange={(evento) => setDiasGracia(evento.target.value)}
                  disabled={!puedeEditar}
                  className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal disabled:bg-slate-100"
                />
              </label>
            </div>
          </div>

          {puedeEditar ? (
            <button className="flex w-full items-center justify-center gap-2 rounded-xl bg-blue-600 px-4 py-3 text-sm font-bold text-white shadow-sm hover:bg-blue-700">
              <Save className="h-4 w-4" /> Guardar configuración
            </button>
          ) : (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-3 text-center text-xs font-semibold text-slate-600">
              Vista de solo lectura. La configuración está reservada para SuperAdmin.
            </div>
          )}
        </form>
      </section>

      <aside className="space-y-4">
        <div className="rounded-2xl border border-blue-200 bg-blue-50 p-5 text-sm text-blue-950">
          <div className="flex items-start gap-3">
            <Info className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
            <div>
              <p className="font-bold">Integración pendiente</p>
              <p className="mt-1 text-xs leading-relaxed text-blue-800">
                Esta pantalla ya permite validar el flujo, pero todavía no guarda datos de forma permanente. El backend deberá devolver el identificador del condominio y confirmar que quedó activo.
              </p>
            </div>
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Estado de configuración</p>
          {configuracion ? (
            <div className="mt-4 space-y-3 text-xs">
              <div className="flex items-center gap-2 text-emerald-700">
                <CheckCircle2 className="h-5 w-5" />
                <span className="font-bold">Validación de frontend completada</span>
              </div>
              <div className="rounded-xl bg-slate-50 p-4 text-slate-700">
                <p className="font-bold text-slate-900">{configuracion.nombre}</p>
                <p className="mt-1">{configuracion.direccion}</p>
                <p className="mt-2">Moneda: {configuracion.moneda}</p>
                <p>Día de corte: {configuracion.diaCorte}</p>
                <p>Días de gracia: {configuracion.diasGracia}</p>
                <span className="mt-3 inline-flex rounded-full bg-emerald-100 px-2.5 py-1 text-[10px] font-bold text-emerald-800">
                  ACTIVO · PENDIENTE DE API
                </span>
              </div>
            </div>
          ) : (
            <div className="mt-4 flex flex-col items-center rounded-xl border border-dashed border-slate-300 px-4 py-8 text-center text-slate-400">
              <Building2 className="h-8 w-8" />
              <p className="mt-2 text-xs">Completa el formulario para previsualizar la configuración.</p>
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
