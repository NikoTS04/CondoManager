"use client";

import { useEffect, useState } from "react";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, Select } from "@/components/ui/Field";
import { consultarProrrateo, exportarProrrateo, type ReporteProrrateo, type Moneda } from "@/lib/api";
import { addMoney } from "@/lib/money";

export function ProrrateoPreview({ presupuestoId, moneda }: { presupuestoId: string; moneda: Moneda }) {
  const [reporte, setReporte] = useState<ReporteProrrateo | null>(null);
  const [edificioId, setEdificioId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [exportando, setExportando] = useState(false);
  const [errorExportacion, setErrorExportacion] = useState<string | null>(null);
  useEffect(() => {
    let vigente = true;
    consultarProrrateo(presupuestoId).then((data) => {
      if (vigente) { setReporte(data); setEdificioId(data.edificios[0]?.id ?? ""); }
    }).catch((cause) => { if (vigente) setError(cause.message); });
    return () => { vigente = false; };
  }, [presupuestoId]);
  if (error) return <Alert tone="danger">{error}</Alert>;
  if (!reporte) return <p role="status">Calculando prorrateo…</p>;
  async function descargar(formato: "pdf" | "docx") {
    if (!reporte || exportando) return;
    setExportando(true); setErrorExportacion(null);
    try { await exportarProrrateo(presupuestoId, reporte.version, formato, edificioId); }
    catch (cause) { setErrorExportacion(cause instanceof Error ? cause.message : "No se pudo exportar."); }
    finally { setExportando(false); }
  }
  const filas = reporte.items.flatMap((i) => i.asignaciones.filter((a) => a.edificio_id === edificioId).map((a) => ({ item: i, asignacion: a })));
  return <section className="space-y-3" aria-label="Previsualización de prorrateo">
    <h3 className="font-semibold">Prorrateo · versión {reporte.version} · {reporte.estado}</h3>
    <Field label="Edificio del reporte"><Select disabled={exportando} value={edificioId} onChange={(e) => setEdificioId(e.target.value)}>{reporte.edificios.map((e) => <option key={e.id} value={e.id}>{e.nombre} · {e.pisos} pisos</option>)}</Select></Field>
    <div className="flex gap-2"><Button type="button" variant="secondary" disabled={exportando || !edificioId} onClick={() => void descargar("pdf")}>Descargar PDF</Button><Button type="button" variant="secondary" disabled={exportando || !edificioId} onClick={() => void descargar("docx")}>Descargar DOCX</Button></div>
    {exportando && <p role="status">Generando documento…</p>}
    {errorExportacion && <Alert tone="danger">{errorExportacion}</Alert>}
    <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <caption className="sr-only">Detalle calculado de mantenimiento por edificio</caption>
      <thead><tr><th scope="col" className="p-2">Concepto</th><th scope="col" className="p-2">Condominio</th><th scope="col" className="p-2">Edificio</th><th scope="col" className="p-2">Unitario</th></tr></thead>
      {["AACC", "EDIFICIO", "CRONOGRAMA_AACC"].map((seccion) => <tbody key={seccion}>
        <tr><th colSpan={4} scope="colgroup" className="bg-canvas p-2">{seccion.replaceAll("_", " ")}</th></tr>
        {filas.filter((f) => f.item.seccion === seccion).map(({ item: i, asignacion: a }) => <tr key={i.id} className="border-b border-line">
          <th scope="row" className="p-2 font-normal">{i.codigo} · {i.descripcion}</th>
          <td className="p-2">{i.metodo_asignacion === "DIRECTO_EDIFICIO" ? "—" : <MoneyAmount value={`${i.tipo_movimiento === "ABONO" ? "-" : ""}${i.monto_periodo}`} moneda={moneda} />}</td>
          <td className="p-2"><MoneyAmount value={a.monto} moneda={moneda} /></td>
          <td className="p-2"><MoneyAmount value={a.unitario} moneda={moneda} /><span className="block text-xs text-muted">{a.unidades} unidades</span></td>
        </tr>)}
        <tr><th scope="row" colSpan={2} className="p-2">Subtotal</th><td className="p-2"><MoneyAmount value={addMoney(...filas.filter((f) => f.item.seccion === seccion).map((f) => f.asignacion.monto))} moneda={moneda} /></td><td /></tr>
      </tbody>)}
      <tfoot><tr><th scope="row" colSpan={2} className="p-2">Total del edificio</th><td className="p-2"><MoneyAmount value={addMoney(...filas.map((f) => f.asignacion.monto))} moneda={moneda} /></td><td /></tr></tfoot>
    </table></div>
    <p className="text-xs text-muted">El unitario es una referencia redondeada. Los cargos individuales conservan el cierre exacto de centavos. PDF y DOCX usan esta misma versión.</p>
  </section>;
}
