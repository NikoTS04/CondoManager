"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { invitarUsuario, listarInvitaciones, modificarInvitacion, type InvitacionUsuario } from "@/lib/api";

const VACIO = { nombre: "", apellido: "", email: "", documento_identidad: "", telefono: "" };

export function InvitacionesSection({ condominioId, onCambio }: { condominioId: string; onCambio: () => void }) {
  const [form, setForm] = useState(VACIO);
  const [invitaciones, setInvitaciones] = useState<InvitacionUsuario[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const [pagina, setPagina] = useState(0);
  const operacion = useRef({ huella: "", clave: "" });

  useEffect(() => {
    let vigente = true;
    setLoading(true);
    listarInvitaciones(condominioId, pagina * 50)
      .then((data) => { if (vigente) setInvitaciones(data); })
      .catch((cause) => { if (vigente) setError(cause instanceof Error ? cause.message : "No se pudieron cargar las invitaciones."); })
      .finally(() => { if (vigente) setLoading(false); });
    return () => { vigente = false; };
  }, [condominioId, pagina, revision]);

  async function ejecutar(huella: string, accion: (clave: string) => Promise<InvitacionUsuario>) {
    if (busy) return;
    if (operacion.current.huella !== huella) operacion.current = { huella, clave: crypto.randomUUID() };
    setBusy(true);
    setError(null);
    setMensaje(null);
    try {
      const resultado = await accion(operacion.current.clave);
      setMensaje(resultado.estado === "REVOCADA" ? "Invitación revocada. Su enlace ya no permite activar la cuenta." : "Invitación registrada y correo encolado. Puedes seguir el estado del envío en Comunicaciones.");
      operacion.current = { huella: "", clave: "" };
      setRevision((value) => value + 1);
      onCambio();
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo completar la operación. Puedes reintentar.");
      return false;
    } finally { setBusy(false); }
  }

  async function invitar(event: FormEvent) {
    event.preventDefault();
    const datos = { ...form, telefono: form.telefono.trim() || null };
    if (await ejecutar(JSON.stringify(datos), (clave) => invitarUsuario(condominioId, datos, clave))) {
      setForm(VACIO);
      setPagina(0);
    }
  }

  return <Card>
    <CardHeader title="Invitar usuario" description="La persona recibe un enlace de un solo uso y elige su contraseña. El acceso inicial es de residente, sin departamentos asignados." />
    <CardBody className="space-y-6">
      {error && <Alert tone="danger">{error}</Alert>}
      {mensaje && <Alert tone="success">{mensaje}</Alert>}
      <form onSubmit={invitar} className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Nombre" required><Input required value={form.nombre} maxLength={80} disabled={busy} onChange={(e) => setForm({ ...form, nombre: e.target.value })} /></Field>
          <Field label="Apellido" required><Input required value={form.apellido} maxLength={80} disabled={busy} onChange={(e) => setForm({ ...form, apellido: e.target.value })} /></Field>
          <Field label="Correo electrónico" required><Input type="email" required value={form.email} maxLength={120} disabled={busy} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="Documento de identidad" required hint="De 6 a 20 caracteres: letras, números o guiones."><Input required value={form.documento_identidad} minLength={6} maxLength={20} disabled={busy} onChange={(e) => setForm({ ...form, documento_identidad: e.target.value })} /></Field>
          <Field label="Teléfono"><Input type="tel" value={form.telefono} maxLength={20} disabled={busy} onChange={(e) => setForm({ ...form, telefono: e.target.value })} /></Field>
        </div>
        <Button type="submit" loading={busy} disabled={busy} loadingText="Guardando…">Enviar invitación</Button>
      </form>
      <div className="flex items-center justify-between gap-3"><h3 className="font-semibold">Historial de invitaciones</h3><Button variant="secondary" disabled={busy || loading} onClick={() => setRevision((v) => v + 1)}>Actualizar invitaciones</Button></div>
      {loading ? <p role="status">Cargando invitaciones…</p> : invitaciones.length === 0 ? <p className="text-sm text-muted">No hay invitaciones en esta página.</p> : <ul className="divide-y divide-line">
        {invitaciones.map((invitacion) => <li key={invitacion.id} className="flex flex-wrap items-center justify-between gap-3 py-3">
          <div className="min-w-0 space-y-1"><p className="break-all text-sm font-medium">{invitacion.email}</p>
            <p className="text-xs text-muted">Vence: {new Date(invitacion.expira_en).toLocaleString("es-PE", { timeZone: "America/Lima" })} · Correo: {invitacion.estado_correo}</p>
            <Badge tone={invitacion.estado === "UTILIZADA" ? "success" : "neutral"}>{invitacion.estado}</Badge></div>
          {invitacion.estado !== "UTILIZADA" && <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" disabled={busy} onClick={() => void ejecutar(`reenviar:${invitacion.id}`, (clave) => modificarInvitacion(condominioId, invitacion.id, true, clave))}>Reenviar</Button>
            {invitacion.estado !== "REVOCADA" && <Button size="sm" variant="ghost" disabled={busy} onClick={() => void ejecutar(`revocar:${invitacion.id}`, (clave) => modificarInvitacion(condominioId, invitacion.id, false, clave))}>Revocar invitación</Button>}
          </div>}
        </li>)}
      </ul>}
      <div className="flex items-center justify-between"><Button variant="secondary" disabled={busy || loading || pagina === 0} onClick={() => setPagina((p) => p - 1)}>Anteriores</Button><span className="text-sm text-muted">Página {pagina + 1}</span><Button variant="secondary" disabled={busy || loading || invitaciones.length < 50} onClick={() => setPagina((p) => p + 1)}>Siguientes</Button></div>
    </CardBody>
  </Card>;
}
