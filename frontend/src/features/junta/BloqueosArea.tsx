"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { crearBloqueo, levantarBloqueo, listarBloqueos, type AreaComun, type BloqueoArea } from "@/lib/api";

export function BloqueosArea({ cid, area, soloLectura }: { cid: string; area: AreaComun; soloLectura: boolean }) {
  const [filas, setFilas] = useState<BloqueoArea[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let vigente = true;
    setLoading(true);
    setError(null);
    listarBloqueos(cid, area.id).then((data) => { if (vigente) setFilas(data); })
      .catch((e) => { if (vigente) setError(e instanceof Error ? e.message : "No se pudieron consultar bloqueos."); })
      .finally(() => { if (vigente) setLoading(false); });
    return () => { vigente = false; };
  }, [cid, area.id, revision]);

  async function guardar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || soloLectura) return;
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true); setError(null);
    try {
      await crearBloqueo(cid, area.id, {
        inicio: `${data.get("inicio")}:00-05:00`,
        fin: `${data.get("fin")}:00-05:00`, motivo: String(data.get("motivo")),
      });
      form.reset(); setRevision((r) => r + 1);
    } catch (e) { setError(e instanceof Error ? e.message : "No se confirmó el bloqueo. Consulte el historial antes de reintentar."); }
    finally { setBusy(false); }
  }

  async function liberar(id: string) {
    if (busy || soloLectura) return;
    setBusy(true); setError(null);
    try { await levantarBloqueo(cid, area.id, id); setRevision((r) => r + 1); }
    catch (e) { setError(e instanceof Error ? e.message : "No se confirmó la liberación."); }
    finally { setBusy(false); }
  }

  const fecha = (valor: string) => new Intl.DateTimeFormat("es-PE", {
    timeZone: "America/Lima", dateStyle: "short", timeStyle: "short",
  }).format(new Date(valor));

  return <Card>
    <CardHeader title={`Mantenimiento: ${area.nombre}`} description="Hora de Lima. No se cancelan reservas automáticamente; un conflicto requiere resolverlas primero." />
    <CardBody className="space-y-4">
      {error && <Alert tone="danger">{error}<Button onClick={() => setRevision((r) => r + 1)}>Consultar de nuevo</Button></Alert>}
      {!soloLectura && <form onSubmit={guardar} className="grid gap-3 sm:grid-cols-2">
        <Field label="Inicio (Lima)" required><Input name="inicio" type="datetime-local" step={60} /></Field>
        <Field label="Fin (Lima)" required><Input name="fin" type="datetime-local" step={60} /></Field>
        <Field label="Motivo auditado" required><Input name="motivo" maxLength={500} /></Field>
        <Button type="submit" disabled={busy || loading}>Crear bloqueo</Button>
      </form>}
      {loading ? <p role="status">Consultando bloqueos…</p> : !error && filas.length === 0 ? <p>No hay bloqueos registrados.</p> : <ul className="space-y-3">
        {filas.map((fila) => <li key={fila.id} className="flex flex-wrap items-center justify-between gap-3">
          <span>{fecha(fila.inicio)} — {fecha(fila.fin)} · {fila.activo ? "Activo" : "Levantado"}</span>
          {!soloLectura && fila.activo && <Button variant="secondary" disabled={busy} onClick={() => void liberar(fila.id)}>Levantar bloqueo</Button>}
        </li>)}
      </ul>}
    </CardBody>
  </Card>;
}
