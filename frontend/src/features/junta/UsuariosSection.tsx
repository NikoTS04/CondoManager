"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { cambiarEstadoUsuario, crearUsuario, listarUsuarios, type CuentaUsuario } from "@/lib/api";

interface Props {
  condominioId: string | null;
  esSuperAdmin: boolean;
}

const VACIO = { nombre: "", apellido: "", email: "", documento_identidad: "", telefono: "", password: "" };
const POR_PAGINA = 50;

export function UsuariosSection({ condominioId, esSuperAdmin }: Props) {
  const [usuarios, setUsuarios] = useState<CuentaUsuario[]>([]);
  const [form, setForm] = useState(VACIO);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [pagina, setPagina] = useState(0);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (!condominioId) return;
    let vigente = true;
    setLoading(true);
    setError(null);
    listarUsuarios(condominioId, POR_PAGINA, pagina * POR_PAGINA)
      .then((data) => { if (vigente) setUsuarios(data); })
      .catch((cause) => { if (vigente) setError(cause instanceof Error ? cause.message : "No se pudieron consultar los usuarios."); })
      .finally(() => { if (vigente) setLoading(false); });
    return () => { vigente = false; };
  }, [condominioId, pagina, revision]);

  const actualizar = useCallback(() => setRevision((value) => value + 1), []);

  async function registrar(event: FormEvent) {
    event.preventDefault();
    if (!condominioId || busy) return;
    setBusy("crear");
    setError(null);
    setMensaje(null);
    try {
      await crearUsuario(condominioId, { ...form, telefono: form.telefono.trim() || null });
      setForm(VACIO);
      setPagina(0);
      actualizar();
      setMensaje("Cuenta creada inactiva. Un SuperAdmin debe habilitarla para permitir el inicio de sesión.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo crear la cuenta.");
    } finally {
      setBusy(null);
    }
  }

  async function cambiarEstado(usuario: CuentaUsuario) {
    if (!condominioId || !esSuperAdmin || busy) return;
    setBusy(usuario.id);
    setError(null);
    setMensaje(null);
    try {
      const cuenta = await cambiarEstadoUsuario(condominioId, usuario.id, !usuario.esta_activo);
      setUsuarios((actuales) => actuales.map((item) => item.id === cuenta.id ? cuenta : item));
      setMensaje(cuenta.esta_activo
        ? `Acceso habilitado para ${cuenta.nombre}. Puede iniciar una nueva sesión.`
        : `Cuenta de ${cuenta.nombre} desactivada. Sus sesiones anteriores han sido invalidadas.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo cambiar el estado.");
    } finally {
      setBusy(null);
    }
  }

  if (!condominioId) {
    return <Alert tone="info">Selecciona un condominio en Configuración para administrar sus usuarios.</Alert>;
  }

  return (
    <div className="space-y-6">
      {error && <Alert tone="danger" title="No se completó la operación">{error}</Alert>}
      {mensaje && <Alert tone="success" title="Resultado">{mensaje}</Alert>}
      <Card>
        <CardHeader title="Registrar usuario" description="La cuenta se crea inactiva, con rol Residente. La contraseña inicial la establece la administración." />
        <CardBody>
          <form onSubmit={registrar} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Nombre" required><Input value={form.nombre} maxLength={80} onChange={(e) => setForm({ ...form, nombre: e.target.value })} /></Field>
              <Field label="Apellido" required><Input value={form.apellido} maxLength={80} onChange={(e) => setForm({ ...form, apellido: e.target.value })} /></Field>
              <Field label="Correo electrónico" required><Input type="email" value={form.email} maxLength={120} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
              <Field label="Documento de identidad" required hint="De 6 a 20 caracteres: letras, números o guiones."><Input value={form.documento_identidad} minLength={6} maxLength={20} onChange={(e) => setForm({ ...form, documento_identidad: e.target.value })} /></Field>
              <Field label="Teléfono"><Input type="tel" value={form.telefono} maxLength={20} onChange={(e) => setForm({ ...form, telefono: e.target.value })} /></Field>
              <Field label="Contraseña inicial" required hint="De 8 a 128 caracteres."><Input type="password" autoComplete="new-password" value={form.password} minLength={8} maxLength={128} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
            </div>
            <Button type="submit" disabled={busy !== null} loading={busy === "crear"}>Crear cuenta inactiva</Button>
          </form>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Usuarios del condominio" description="El estado habilita el acceso completo a la cuenta. La verificación por correo se incorporará posteriormente." />
        <CardBody>
          <div className="mb-4 flex items-center justify-between gap-3">
            <p className="text-sm text-muted">{esSuperAdmin ? "Puedes activar o desactivar cuentas. El cambio afecta a todos los condominios de esa persona." : "Solo SuperAdmin puede cambiar el estado de las cuentas."}</p>
            <Button variant="secondary" onClick={actualizar} disabled={loading || busy !== null}>Actualizar</Button>
          </div>
          {loading ? <p role="status">Cargando usuarios…</p> : usuarios.length === 0 ? <p>No hay usuarios en esta página.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Usuarios y estado de acceso del condominio</caption>
                <thead><tr className="border-b border-line"><th scope="col" className="p-3">Nombre</th><th scope="col" className="p-3">Correo</th><th scope="col" className="p-3">Documento</th><th scope="col" className="p-3">Estado</th>{esSuperAdmin && <th scope="col" className="p-3">Acciones</th>}</tr></thead>
                <tbody>{usuarios.map((usuario) => (
                  <tr key={usuario.id} className="border-b border-line">
                    <td className="p-3">{usuario.nombre} {usuario.apellido}</td><td className="p-3">{usuario.email}</td><td className="p-3">{usuario.documento_identidad}</td>
                    <td className="p-3"><Badge tone={usuario.esta_activo ? "success" : "neutral"}>{usuario.esta_activo ? "Activo" : "Inactivo"}</Badge></td>
                    {esSuperAdmin && <td className="p-3"><Button variant="secondary" disabled={busy !== null} loading={busy === usuario.id} onClick={() => void cambiarEstado(usuario)} aria-label={`${usuario.esta_activo ? "Desactivar" : "Activar"} a ${usuario.nombre} ${usuario.apellido}`}>{usuario.esta_activo ? "Desactivar" : "Activar"}</Button></td>}
                  </tr>
                ))}</tbody>
              </table>
            </div>
          )}
          <div className="mt-4 flex items-center justify-between gap-3">
            <Button variant="secondary" disabled={pagina === 0 || loading || busy !== null} onClick={() => setPagina((value) => value - 1)}>Anterior</Button>
            <span className="text-sm text-muted">Página {pagina + 1}</span>
            <Button variant="secondary" disabled={usuarios.length < POR_PAGINA || loading || busy !== null} onClick={() => setPagina((value) => value + 1)}>Siguiente</Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}
