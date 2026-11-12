"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { consultarCondicionesPago, guardarCondicionesPago, type CondicionesPago } from "@/lib/api";

export function CondicionesPagoForm({ departamentoId, vinculoId }: { departamentoId: string; vinculoId: string }) {
  const [datos, setDatos] = useState<CondicionesPago | null>(null);
  const [gracia, setGracia] = useState("");
  const [motivo, setMotivo] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let vigente = true;
    setDatos(null);
    setError(null);
    consultarCondicionesPago(departamentoId).then((actual) => {
      if (!vigente) return;
      setDatos(actual);
      setGracia(actual.vinculo_responsable_id === vinculoId && actual.dias_gracia_override !== null ? String(actual.dias_gracia_override) : "");
    }).catch((cause) => { if (vigente) setError(cause.message); });
    return () => { vigente = false; };
  }, [departamentoId, vinculoId, revision]);

  async function guardar(retirar = false) {
    if (!datos || busy) return;
    const dias = gracia === "" ? null : Number(gracia);
    if (!retirar && dias !== null && (!Number.isInteger(dias) || dias < 0 || dias > 30)) {
      setError("Los días de gracia deben ser un entero entre 0 y 30, o vacío para heredar.");
      return;
    }
    if (!motivo.trim()) { setError("Indique el motivo del cambio."); return; }
    setBusy(true); setError(null); setMensaje(null);
    try {
      const actual = await guardarCondicionesPago(departamentoId, {
        vinculo_responsable_id: retirar ? null : vinculoId,
        dias_gracia_override: retirar ? null : dias,
        version_esperada: datos.version, motivo,
      });
      setDatos(actual);
      setMotivo("");
      setMensaje("Condiciones guardadas para nuevas emisiones. Las cuotas anteriores no cambian.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo guardar. Recargue antes de reintentar.");
    } finally { setBusy(false); }
  }

  function enviar(event: FormEvent) { event.preventDefault(); void guardar(); }

  return <div className="space-y-4 text-left">
    {error && <Alert tone="danger" title="No se completó el cambio">{error}</Alert>}
    {mensaje && <Alert tone="success">{mensaje}</Alert>}
    <Button variant="secondary" disabled={busy} onClick={() => setRevision(revision + 1)}>Recargar condiciones</Button>
    {datos && <>
      <p>Gracia efectiva actual: {datos.dias_gracia_efectivos} días.</p>
      {datos.vinculo_responsable_id && datos.vinculo_responsable_id !== vinculoId && <Alert tone="warning">Hay otro vínculo designado como responsable. Guardar lo reemplazará por el usuario seleccionado.</Alert>}
      <form onSubmit={enviar} className="space-y-4">
        <Field label="Días de gracia individuales (vacío: heredar global)">
          <Input inputMode="numeric" value={gracia} disabled={busy} onChange={(event) => setGracia(event.target.value)} />
        </Field>
        <p className="text-sm text-muted">0 elimina la gracia para nuevas cuotas. La unidad sigue teniendo una sola obligación por periodo.</p>
        <Field label="Motivo" required><Textarea required maxLength={1000} value={motivo} disabled={busy} onChange={(event) => setMotivo(event.target.value)} /></Field>
        <div className="flex flex-wrap gap-2">
          <Button type="submit" loading={busy}>Designar este vínculo y guardar</Button>
          {datos.vinculo_responsable_id === vinculoId && <Button variant="secondary" disabled={busy} onClick={() => void guardar(true)}>Retirar designación e heredar global</Button>}
        </div>
      </form>
    </>}
    {!datos && !error && <p role="status">Cargando condiciones de pago…</p>}
  </div>;
}
