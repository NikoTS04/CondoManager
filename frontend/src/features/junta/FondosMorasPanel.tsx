"use client";

import { useEffect, useRef, useState } from "react";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { MoneyInput } from "@/components/ui/MoneyInput";
import { consultarFondoMoras, consultarProrrateo, liberarMoras, listarAplicacionesMoras, reservarMoras,
  type AplicacionMoras, type ItemPresupuesto, type Moneda, type ReporteProrrateo, type ResumenFondoMoras } from "@/lib/api";
import { isPositiveMoney, normalizeMoney } from "@/lib/money";

export function FondosMorasPanel({ presupuestoId, version, periodo, moneda, items, soloLectura, disabled, onActualizado, onBusy }: {
  presupuestoId: string; version: number; periodo: string; moneda: Moneda; items: ItemPresupuesto[];
  soloLectura: boolean; disabled: boolean; onActualizado: () => Promise<void>; onBusy: (busy: boolean) => void;
}) {
  const [reporte, setReporte] = useState<ReporteProrrateo | null>(null);
  const [aplicaciones, setAplicaciones] = useState<AplicacionMoras[]>([]);
  const [edificioId, setEdificioId] = useState("");
  const [fondo, setFondo] = useState<ResumenFondoMoras | null>(null);
  const [itemId, setItemId] = useState("");
  const [monto, setMonto] = useState("");
  const [motivo, setMotivo] = useState("");
  const [busy, setBusy] = useState(false);
  const [recarga, setRecarga] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const pendiente = useRef<{ cuerpo: string; clave: string } | null>(null);

  useEffect(() => {
    let vigente = true;
    setReporte(null); setError(null);
    Promise.all([consultarProrrateo(presupuestoId), listarAplicacionesMoras(presupuestoId)]).then(([r, a]) => {
      if (!vigente) return;
      setReporte(r); setAplicaciones(a);
      setEdificioId((id) => r.edificios.some((e) => e.id === id) ? id : r.edificios[0]?.id ?? "");
    }).catch((cause) => { if (vigente) setError(cause instanceof Error ? cause.message : "No se pudo consultar las coberturas."); });
    return () => { vigente = false; };
  }, [presupuestoId, version, recarga]);

  useEffect(() => {
    let vigente = true;
    setFondo(null);
    if (edificioId) consultarFondoMoras(edificioId, periodo).then((r) => { if (vigente) setFondo(r); })
      .catch((cause) => { if (vigente) setError(cause instanceof Error ? cause.message : "No se pudo consultar el fondo."); });
    return () => { vigente = false; };
  }, [edificioId, periodo, version, recarga]);

  async function operar(accion: () => Promise<unknown>) {
    if (busy) return;
    setBusy(true); onBusy(true); setError(null); setMensaje(null);
    try {
      await accion();
      await onActualizado();
      setRecarga((n) => n + 1);
      setMensaje("Fondos y presupuesto actualizados.");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo actualizar el fondo."); }
    finally { setBusy(false); onBusy(false); }
  }

  async function reservar() {
    const payload = { version_esperada: version, item_id: itemId, edificio_id: edificioId,
      monto: normalizeMoney(monto), motivo: motivo.trim() };
    const cuerpo = JSON.stringify(payload);
    if (pendiente.current?.cuerpo !== cuerpo) pendiente.current = { cuerpo, clave: crypto.randomUUID() };
    await reservarMoras(presupuestoId, pendiente.current.clave, payload);
    pendiente.current = null;
    setMonto(""); setMotivo("");
  }

  const bloqueado = disabled || busy || !reporte || !fondo;
  return <section aria-label="Fondos de moras cobradas" className="space-y-3 rounded-xl border border-line p-4"
    onKeyDown={(event) => { if (event.key === "Enter" && event.target instanceof HTMLInputElement) event.preventDefault(); }}>
    <div className="flex flex-wrap items-center justify-between gap-2"><h3 className="font-semibold">Financiar gastos con moras cobradas</h3>
      <Button type="button" size="sm" variant="secondary" disabled={disabled || busy} onClick={() => void operar(async () => undefined)}>Actualizar</Button></div>
    <p className="text-sm text-muted">Solo cobros conciliados. Reservar reduce el cargo a residentes; aprobar confirma sin descontar dos veces. No se importa caja histórica.</p>
    {error && <Alert tone="danger">{error}</Alert>}
    {mensaje && <Alert tone="success">{mensaje}</Alert>}
    {!reporte && !error && <p role="status">Consultando coberturas…</p>}
    <Field label="Edificio del fondo"><Select disabled={busy || !reporte} value={edificioId} onChange={(e) => setEdificioId(e.target.value)}>
      {reporte?.edificios.map((e) => <option key={e.id} value={e.id}>{e.nombre}</option>)}
    </Select></Field>
    {fondo && <dl className="grid gap-3 rounded-lg bg-canvas p-3 text-sm sm:grid-cols-2">
      {[['Disponible', fondo.saldo_disponible], ['Reservado', fondo.saldo_reservado], ['Aplicado a gastos', fondo.total_aplicado], ['Mora pendiente (no es caja)', fondo.mora_pendiente_cobro]].map(([label, value]) =>
        <div key={label}><dt className="text-muted">{label}</dt><dd className="font-semibold"><MoneyAmount value={value} moneda={moneda} /></dd></div>)}
    </dl>}
    {!soloLectura && <fieldset disabled={bloqueado} className="grid gap-3 sm:grid-cols-2">
      <legend className="sr-only">Reservar cobertura de un gasto guardado</legend>
      <Field label="Gasto a cubrir"><Select value={itemId} onChange={(e) => setItemId(e.target.value)}><option value="">Seleccione un cargo</option>
        {items.filter((i) => i.tipo_movimiento === "CARGO" && (i.metodo_asignacion !== "DIRECTO_EDIFICIO" || i.edificio_id === edificioId))
          .map((i) => <option key={i.id} value={i.id}>{reporte?.items.find((r) => r.id === i.id)?.descripcion ?? i.descripcion ?? i.id}</option>)}
      </Select></Field>
      <Field label="Importe a cubrir"><MoneyInput value={monto} moneda={moneda} onValueChange={setMonto} /></Field>
      <Field label="Motivo de la cobertura"><Input value={motivo} maxLength={1000} onChange={(e) => setMotivo(e.target.value)} /></Field>
      <Button type="button" variant="secondary" disabled={!itemId || !edificioId || !isPositiveMoney(monto) || !motivo.trim()} onClick={() => void operar(reservar)}>Reservar cobertura</Button>
    </fieldset>}
    <ul className="space-y-2" aria-label="Coberturas registradas">
      {aplicaciones.filter((a) => a.edificio_id === edificioId).map((a) => <li key={a.id} className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-2 text-sm">
        <div><span className="font-medium">{reporte?.items.find((i) => i.id === a.item_id)?.descripcion ?? "Ítem retirado"}</span> · <MoneyAmount value={a.monto} moneda={moneda} /> · {a.estado}
          <p className="text-muted">{a.motivo}</p></div>
        {!soloLectura && a.estado === "RESERVADA" && <Button type="button" size="sm" variant="secondary" disabled={bloqueado}
          onClick={() => void operar(() => liberarMoras(presupuestoId, a.id, version))}>Liberar reserva</Button>}
      </li>)}
    </ul>
    {fondo && <details><summary className="cursor-pointer text-sm">Movimientos de {periodo}</summary>
      <ul className="mt-2 space-y-1 text-sm">{fondo.movimientos?.map((m) => <li key={m.id}>{m.fecha_local} · {m.tipo} · <MoneyAmount value={m.importe} moneda={moneda} /></li>)}</ul>
      {!fondo.movimientos?.length && <p className="text-sm text-muted">Sin movimientos reconocidos en este periodo.</p>}
    </details>}
    {disabled && <p className="text-sm text-muted">Guarda los cambios del presupuesto antes de cambiar coberturas.</p>}
  </section>;
}
