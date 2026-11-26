"use client";

import { useState } from "react";
import { listarCargosIncidencias, type CargoIncidencia, type ComprobantePago } from "@/lib/api";
import { formatMoney } from "@/lib/money";

export function DestinosPago({ comprobante }: { comprobante: ComprobantePago }) {
  const ids = comprobante.cargos_incidencia_ids || [];
  const [cargos, setCargos] = useState<CargoIncidencia[] | null>(null);
  const [error, setError] = useState("");
  const [cargando, setCargando] = useState(false);
  if (ids.length === 0) return <p className="text-xs font-normal text-muted">Pago de cuotas</p>;

  async function consultar(abierto: boolean) {
    if (!abierto || cargos || cargando) return;
    setCargando(true);
    setError("");
    try {
      const lista = await listarCargosIncidencias(comprobante.departamento_id);
      setCargos(lista.filter((c) => ids.includes(c.id)));
    } catch {
      setError("No pudimos consultar los conceptos. Cierra y vuelve a abrir para reintentar.");
    } finally { setCargando(false); }
  }

  return (
    <details className="mt-1 text-xs font-normal" onToggle={(e) => void consultar(e.currentTarget.open)}>
      <summary className="cursor-pointer text-brand-700">Pago dirigido · {ids.length} concepto(s) de incidencias</summary>
      {cargando && <p role="status">Cargando conceptos…</p>}
      {error && <p role="alert">{error}</p>}
      <ul className="mt-1 space-y-1">
        {cargos?.map((c) => <li key={c.id}>{c.concepto} · {formatMoney(c.monto, c.moneda)}</li>)}
      </ul>
    </details>
  );
}
