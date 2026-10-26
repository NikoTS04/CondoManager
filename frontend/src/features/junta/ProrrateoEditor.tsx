"use client";

import { useEffect, useState } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { MoneyInput } from "@/components/ui/MoneyInput";
import { crearConceptoPresupuestal, listarConceptosPresupuestales, listarEdificios,
  type ConceptoPresupuestal, type Edificio, type ItemPresupuesto, type Moneda } from "@/lib/api";

const CATEGORIAS = ["SERVICIOS_BASICOS", "MANTENIMIENTO_PREVENTIVO", "SEGURIDAD_Y_VIGILANCIA", "LIMPIEZA_Y_JARDINERIA", "GASTOS_ADMINISTRATIVOS", "IMPREVISTOS_Y_CONTINGENCIAS", "OBLIGACIONES_FINANCIADAS"];

export function ProrrateoEditor({ cid, items, onChange, disabled, moneda }: {
  cid: string; items: ItemPresupuesto[]; onChange: (items: ItemPresupuesto[]) => void; disabled: boolean; moneda: Moneda;
}) {
  const [conceptos, setConceptos] = useState<ConceptoPresupuestal[]>([]);
  const [edificios, setEdificios] = useState<Edificio[]>([]);
  const [seleccion, setSeleccion] = useState("");
  const [codigo, setCodigo] = useState("");
  const [categoria, setCategoria] = useState(CATEGORIAS[0]);
  const [descripcion, setDescripcion] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let vigente = true;
    Promise.all([listarConceptosPresupuestales(cid), listarEdificios(cid)]).then(([catalogo, torres]) => {
      if (vigente) { setConceptos(catalogo); setEdificios(torres); setError(null); }
    }).catch((cause) => { if (vigente) setError(cause.message); });
    return () => { vigente = false; };
  }, [cid]);

  async function registrar() {
    setBusy(true); setError(null);
    try {
      const concepto = await crearConceptoPresupuestal(cid, { codigo, categoria, descripcion });
      setConceptos([...conceptos, concepto]); setSeleccion(concepto.id); setCodigo(""); setDescripcion("");
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo registrar el concepto."); }
    finally { setBusy(false); }
  }

  function cambiar(id: string, cambios: Partial<ItemPresupuesto>) {
    onChange(items.map((item) => item.id === id ? { ...item, ...cambios } : item));
  }

  return <section className="space-y-4 rounded-xl border border-line p-4" aria-label="Detalle del prorrateo">
    <h3 className="font-semibold">Conceptos y reparto</h3>
    <p className="text-sm text-muted">Importes brutos del periodo; los totales y centavos se validan en el servidor. Gestiona la cobertura en Fondos de moras cobradas después de guardar.</p>
    {error && <Alert tone="danger">{error}</Alert>}
    {!disabled && <>
      <details className="rounded border border-line p-3" onKeyDown={(event) => { if (event.key === "Enter" && event.target instanceof HTMLInputElement) event.preventDefault(); }}><summary className="cursor-pointer">Registrar un concepto nuevo</summary>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <Field label="Código estable (ej. AGU-01)"><Input value={codigo} maxLength={30} onChange={(e) => setCodigo(e.target.value.toUpperCase())} /></Field>
          <Field label="Categoría"><Select value={categoria} onChange={(e) => setCategoria(e.target.value)}>{CATEGORIAS.map((c) => <option key={c}>{c}</option>)}</Select></Field>
          <Field label="Descripción"><Input value={descripcion} maxLength={500} onChange={(e) => setDescripcion(e.target.value)} /></Field>
          <Button type="button" variant="secondary" loading={busy} disabled={!codigo || !descripcion.trim()} onClick={() => void registrar()}>Registrar concepto</Button>
        </div>
      </details>
      <div className="flex flex-wrap gap-2">
        <Field label="Concepto a agregar"><Select value={seleccion} onChange={(e) => setSeleccion(e.target.value)}>
          <option value="">Seleccione un concepto</option>{conceptos.filter((c) => c.activo).map((c) => <option key={c.id} value={c.id}>{c.codigo} · {c.descripcion}</option>)}
        </Select></Field>
        <Button type="button" variant="secondary" disabled={!seleccion || items.length >= 500} onClick={() => onChange([...items, {
          id: crypto.randomUUID(), concepto_id: seleccion, monto_periodo: "0.00", seccion: "AACC",
          tipo_movimiento: "CARGO", metodo_asignacion: "POR_PISOS", metodo_unitario: "EQUITATIVA",
        }])}>Agregar ítem</Button>
      </div>
    </>}
    {items.map((item) => {
      const concepto = conceptos.find((c) => c.id === item.concepto_id);
      return <fieldset key={item.id} disabled={disabled} className="space-y-3 rounded-lg border border-line p-3">
        <legend className="px-2 text-sm font-semibold">{concepto?.codigo ?? "Concepto"} · {concepto?.descripcion ?? item.descripcion}</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Sección"><Select value={item.seccion} onChange={(e) => cambiar(item.id, { seccion: e.target.value as ItemPresupuesto["seccion"] })}>
            <option value="AACC">Áreas comunes</option><option value="EDIFICIO">Gastos del edificio</option><option value="CRONOGRAMA_AACC">Cronograma AACC</option>
          </Select></Field>
          <Field label="Movimiento"><Select value={item.tipo_movimiento} onChange={(e) => cambiar(item.id, { tipo_movimiento: e.target.value as ItemPresupuesto["tipo_movimiento"] })}><option value="CARGO">Cargo</option><option value="ABONO">Abono al reparto</option></Select></Field>
          <Field label="Importe del periodo"><MoneyInput moneda={moneda} value={item.monto_periodo} onValueChange={(v) => cambiar(item.id, { monto_periodo: v })} /></Field>
          <Field label="Asignación a edificios"><Select value={item.metodo_asignacion} onChange={(e) => cambiar(item.id, {
            metodo_asignacion: e.target.value as ItemPresupuesto["metodo_asignacion"], asignaciones_explicitas: {},
            edificio_id: e.target.value === "DIRECTO_EDIFICIO" ? edificios[0]?.id ?? null : null,
          })}><option value="POR_PISOS">Común, por pisos</option><option value="DIRECTO_EDIFICIO">Exclusivo del edificio</option>{item.metodo_asignacion === "ASIGNACION_EXPLICITA" && <option value="ASIGNACION_EXPLICITA">Asignación explícita (gestionada por API)</option>}</Select></Field>
          {item.metodo_asignacion === "DIRECTO_EDIFICIO" && <Field label="Edificio"><Select value={item.edificio_id ?? ""} onChange={(e) => cambiar(item.id, { edificio_id: e.target.value })}><option value="">Seleccione</option>{edificios.map((e) => <option key={e.id} value={e.id}>{e.nombre_bloque}</option>)}</Select></Field>}
          <Field label="Reparto dentro del edificio"><Select value={item.metodo_unitario ?? "EQUITATIVA"} onChange={(e) => cambiar(item.id, { metodo_unitario: e.target.value as ItemPresupuesto["metodo_unitario"] })}><option value="EQUITATIVA">Equitativo</option><option value="POR_ALICUOTA">Por coeficiente del edificio</option></Select></Field>
          <Field label="Detalle del mes"><Input value={item.descripcion ?? ""} onChange={(e) => cambiar(item.id, { descripcion: e.target.value })} /></Field>
          <Field label="Suministro / servicio"><Input value={item.referencia_servicio ?? ""} onChange={(e) => cambiar(item.id, { referencia_servicio: e.target.value })} /></Field>
          <Field label="Documento de sustento"><Input value={item.referencia_documento ?? ""} onChange={(e) => cambiar(item.id, { referencia_documento: e.target.value })} /></Field>
          <Field label="Código original"><Input value={item.codigo_origen ?? ""} onChange={(e) => cambiar(item.id, { codigo_origen: e.target.value })} /></Field>
          <Field label="Observaciones"><Input value={item.observacion_origen ?? ""} onChange={(e) => cambiar(item.id, { observacion_origen: e.target.value })} /></Field>
          {concepto?.categoria === "OBLIGACIONES_FINANCIADAS" && <>
            <Field label="Obligación financiada"><Input value={item.obligacion_referencia ?? ""} onChange={(e) => cambiar(item.id, { obligacion_referencia: e.target.value })} /></Field>
            <Field label="Cuota número"><Input type="number" min={1} value={item.numero_cuota ?? ""} onChange={(e) => cambiar(item.id, { numero_cuota: e.target.value ? Number(e.target.value) : null })} /></Field>
            <Field label="Total de cuotas"><Input type="number" min={1} value={item.total_cuotas ?? ""} onChange={(e) => cambiar(item.id, { total_cuotas: e.target.value ? Number(e.target.value) : null })} /></Field>
            <Field label="Importe total de obligación"><MoneyInput moneda={moneda} value={item.monto_total_obligacion ?? ""} onValueChange={(v) => cambiar(item.id, { monto_total_obligacion: v })} /></Field>
          </>}
        </div>
        {item.monto_cubierto_moras && item.monto_cubierto_moras !== "0.00" && <p className="text-sm text-muted">Cobertura registrada: {item.monto_cubierto_moras}. Las reservas se liberan en Fondos de moras; las coberturas confirmadas no se eliminan.</p>}
        {!disabled && <Button type="button" size="sm" variant="danger" disabled={!!item.monto_cubierto_moras && item.monto_cubierto_moras !== "0.00"} onClick={() => onChange(items.filter((i) => i.id !== item.id))}>Quitar ítem del borrador</Button>}
      </fieldset>;
    })}
  </section>;
}
