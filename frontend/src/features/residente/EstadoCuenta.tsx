"use client";

import { useEffect, useState, type FormEvent } from "react";
import { fetchEstadoCuenta, type EstadoCuenta as Cuenta } from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { SkeletonList } from "@/components/ui/Feedback";

function mesActual() {
  const partes = new Intl.DateTimeFormat("en", { timeZone: "America/Lima", year: "numeric", month: "2-digit" }).formatToParts(new Date());
  const year = partes.find((p) => p.type === "year")!.value;
  const month = partes.find((p) => p.type === "month")!.value;
  const ultimo = new Date(Date.UTC(Number(year), Number(month), 0)).getUTCDate();
  return { desde: `${year}-${month}-01`, hasta: `${year}-${month}-${ultimo}` };
}

export function EstadoCuenta({ departamentoId }: { departamentoId: string }) {
  const [rango] = useState(mesActual);
  const [desde, setDesde] = useState(rango.desde);
  const [hasta, setHasta] = useState(rango.hasta);
  const [consulta, setConsulta] = useState({ ...rango, offset: 0 });
  const [revision, setRevision] = useState(0);
  const [resultado, setResultado] = useState<{ clave: string; data: Cuenta } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorFiltro, setErrorFiltro] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);
  const clave = `${departamentoId}:${consulta.desde}:${consulta.hasta}:${consulta.offset}`;
  const data = resultado?.clave === clave ? resultado.data : null;

  useEffect(() => {
    let vigente = true;
    const controller = new AbortController();
    setCargando(true);
    setError(null);
    setResultado(null);
    fetchEstadoCuenta(departamentoId, consulta.desde, consulta.hasta, consulta.offset, controller.signal)
      .then((cuenta) => {
        if (!vigente) return;
        if (cuenta.departamento_id !== departamentoId) throw new Error("La respuesta no corresponde al departamento seleccionado. Vuelve a consultar.");
        if (cuenta.total_movimientos > 0 && cuenta.offset >= cuenta.total_movimientos) {
          setConsulta((q) => ({ ...q, offset: 0 }));
          return;
        }
        setResultado({ clave, data: cuenta });
      })
      .catch((e: unknown) => {
        if (vigente) setError(e instanceof Error ? e.message : "No pudimos cargar los movimientos.");
      })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; controller.abort(); };
  }, [clave, consulta.desde, consulta.hasta, consulta.offset, departamentoId, revision]);

  function filtrar(event: FormEvent) {
    event.preventDefault();
    const dias = (Date.parse(hasta) - Date.parse(desde)) / 86400000;
    if (!desde || !hasta || !Number.isFinite(dias) || dias < 0 || dias >= 366) {
      setErrorFiltro("Elige un rango de 1 a 366 días, con la fecha final igual o posterior a la inicial.");
      return;
    }
    setErrorFiltro(null);
    setConsulta({ desde, hasta, offset: 0 });
    setRevision((r) => r + 1);
  }

  return (
    <Card>
      <CardHeader title="Estado de cuenta" description="Cargos y abonos por fecha de registro en Lima. Los pagos en revisión se muestran por separado."
        actions={<Button variant="secondary" size="sm" onClick={() => setRevision((r) => r + 1)} disabled={cargando}>Actualizar movimientos</Button>} />
      <CardBody className="space-y-6">
        <form onSubmit={filtrar} className="grid items-end gap-3 sm:grid-cols-[1fr_1fr_auto]" aria-label="Filtrar estado de cuenta">
          <Field label="Desde" required><Input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} /></Field>
          <Field label="Hasta" required><Input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} /></Field>
          <Button type="submit">Consultar periodo</Button>
        </form>
        {errorFiltro && <Alert tone="warning">{errorFiltro}</Alert>}
        <div aria-live="polite" aria-busy={cargando}>
          {cargando ? <SkeletonList rows={4} label="Cargando movimientos de la cuenta…" /> : error ? (
            <Alert tone="danger" title="No pudimos consultar tu estado de cuenta" action={<Button variant="secondary" onClick={() => setRevision((r) => r + 1)}>Reintentar</Button>}>{error}</Alert>
          ) : data && (
            <div className="space-y-6">
              <dl className="grid grid-cols-2 gap-4 rounded-lg bg-canvas p-4 lg:grid-cols-4">
                {([
                  ["Saldo inicial", data.saldo_inicial], ["Cargos del periodo", data.cargos_periodo],
                  ["Abonos del periodo", data.abonos_periodo], ["Saldo final", data.saldo_final],
                ] as const).map(([label, value]) => <div key={label}><dt className="text-sm text-muted">{label}</dt><dd className="mt-1 text-lg font-semibold"><MoneyAmount value={value} moneda={data.moneda} /></dd></div>)}
              </dl>
              <p className="text-sm text-muted">Del {formatDate(data.desde)} al {formatDate(data.hasta)}. Un saldo negativo representa saldo a favor. Los saldos actuales pueden incluir operaciones posteriores a este rango.</p>
              {data.base_historica_sin_fecha && <Alert tone="info" title="Importes anteriores sin desglose">
                El saldo inicial incorpora crédito previo de <MoneyAmount value={data.credito_inicial_sin_desglose} moneda={data.moneda} /> y abonos históricos de <MoneyAmount value={data.abonos_historicos_sin_desglose} moneda={data.moneda} /> sin fecha documentada.
                {data.historial_desde && ` Los movimientos disponibles comienzan el ${formatDate(data.historial_desde)}.`}
              </Alert>}
              {data.total_movimientos === 0 ? <Alert tone="info" title="Sin movimientos en este periodo">Prueba con otro rango. El saldo inicial puede provenir de periodos anteriores.</Alert> : (
                <>
                  <div className="overflow-x-auto rounded-lg border border-line">
                    <table className="w-full min-w-[680px] text-sm">
                      <caption className="sr-only">Movimientos del estado de cuenta del departamento seleccionado</caption>
                      <thead className="bg-canvas text-muted"><tr>{["Fecha de registro", "Concepto", "Cargo", "Abono", "Saldo"].map((label, i) => <th key={label} scope="col" className={`px-4 py-3 font-medium ${i > 1 ? "text-right" : "text-left"}`}>{label}</th>)}</tr></thead>
                      <tbody className="divide-y divide-line">{data.movimientos.map((m) => <tr key={m.id}>
                        <td className="whitespace-nowrap px-4 py-3 align-top">{formatDate(m.fecha)}{m.fecha_operacion && <span className="mt-1 block text-xs text-muted">{m.tipo === "PAGO_APROBADO" ? "Operación" : "Devengo"}: {formatDate(m.fecha_operacion)}</span>}</td>
                        <td className="px-4 py-3"><p className="font-medium">{m.descripcion}</p>
                          {m.periodo_cuota && <p className="text-xs text-muted">Periodo de cuota: {m.periodo_cuota}</p>}
                          {m.comprobante_id && <p className="text-xs text-muted" title={m.comprobante_id}>Pago {m.comprobante_id.slice(0, 8)}</p>}
                          {(m.tipo === "DISTRIBUCION_PAGO" || m.tipo === "APLICACION_CREDITO") && <p className="mt-1 text-xs text-muted">Detalle: <MoneyAmount value={m.importe} moneda={data.moneda} />. No suma otro cargo o abono.</p>}
                        </td>
                        <td className="px-4 py-3 text-right align-top"><MoneyAmount value={m.cargo} moneda={data.moneda} /></td>
                        <td className="px-4 py-3 text-right align-top"><MoneyAmount value={m.abono} moneda={data.moneda} /></td>
                        <td className="px-4 py-3 text-right align-top font-medium"><MoneyAmount value={m.saldo} moneda={data.moneda} /></td>
                      </tr>)}</tbody>
                    </table>
                  </div>
                  <div className="flex flex-wrap items-center justify-between gap-3 text-sm">
                    <p className="text-muted">{data.offset + 1}–{Math.min(data.offset + data.movimientos.length, data.total_movimientos)} de {data.total_movimientos} movimientos</p>
                    <div className="flex gap-2"><Button variant="secondary" size="sm" disabled={data.offset === 0} onClick={() => setConsulta((q) => ({ ...q, offset: Math.max(0, q.offset - data.limite) }))}>Anterior</Button><Button variant="secondary" size="sm" disabled={data.offset + data.limite >= data.total_movimientos} onClick={() => setConsulta((q) => ({ ...q, offset: q.offset + data.limite }))}>Siguiente</Button></div>
                  </div>
                </>
              )}
              <section className="space-y-3 border-t border-line pt-5" aria-label="Pagos en revisión del periodo">
                <h3 className="text-sm font-semibold">Pagos en revisión</h3>
                <p className="text-sm text-muted">Reportados en este rango y todavía pendientes de aprobación. No reducen el saldo.</p>
                {data.pagos_en_revision.length ? <ul className="divide-y divide-line">{data.pagos_en_revision.map((p) => <li key={p.id} className="flex flex-wrap justify-between gap-2 py-3 text-sm"><span>{p.banco} · Operación {p.numero_operacion}<span className="block text-xs text-muted">Reportado el {formatDate(p.fecha_reporte)} · Fecha bancaria {formatDate(p.fecha_operacion)}</span></span><MoneyAmount value={p.monto} moneda={data.moneda} /></li>)}</ul> : <p className="text-sm text-muted">Sin pagos en revisión en este rango.</p>}
              </section>
              <p className="text-xs text-muted">Consulta generada el {formatDateTime(data.generado_en)}. No modifica tus movimientos ni recalcula moras.</p>
            </div>
          )}
        </div>
      </CardBody>
    </Card>
  );
}
