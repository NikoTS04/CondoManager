"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import { asignarRolUsuario, cambiarEstadoUsuario, crearUsuario, listarUsuarios, revocarRolUsuario, type CuentaUsuario, type CuentaUsuarioConRol, type RolContextual } from "@/lib/api";
import { RolUsuarioEditor } from "@/features/junta/RolUsuarioEditor";

interface Props {
  condominioId: string | null;
  esSuperAdmin: boolean;
  usuarioActualId: string;
}

const VACIO = { nombre: "", apellido: "", email: "", documento_identidad: "", telefono: "", password: "" };
const POR_PAGINA = 50;

export function UsuariosSection({ condominioId, esSuperAdmin, usuarioActualId }: Props) {
  const [usuarios, setUsuarios] = useState<CuentaUsuarioConRol[]>([]);
  const [form, setForm] = useState(VACIO);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [pagina, setPagina] = useState(0);
  const [revision, setRevision] = useState(0);
  const [identidadId, setIdentidadId] = useState("");
  const [rolExistente, setRolExistente] = useState<RolContextual>("RESIDENTE");

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
      setUsuarios((actuales) => actuales.map((item) => item.id === cuenta.id ? { ...item, ...cuenta } : item));
      setMensaje(cuenta.esta_activo
        ? `Acceso habilitado para ${cuenta.nombre}. Puede iniciar una nueva sesión.`
        : `Cuenta de ${cuenta.nombre} desactivada. Sus sesiones anteriores han sido invalidadas.`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo cambiar el estado.");
    } finally {
      setBusy(null);
    }
  }

  async function guardarRol(usuarioId: string, rol: RolContextual | null): Promise<boolean> {
    if (!condominioId || busy) return false;
    setBusy(`rol:${usuarioId}`);
    setError(null);
    setMensaje(null);
    try {
      const asignacion = rol === null
        ? await revocarRolUsuario(condominioId, usuarioId)
        : await asignarRolUsuario(condominioId, usuarioId, rol);
      setUsuarios((actuales) => actuales.map((item) => item.id === usuarioId
        ? { ...item, rol: asignacion.rol, rol_activo: asignacion.es_activo } : item));
      actualizar();
      setMensaje(asignacion.es_activo
        ? "Rol guardado. El usuario debe iniciar sesión nuevamente para utilizar sus permisos vigentes."
        : "Rol revocado en este condominio. Las sesiones anteriores han sido invalidadas.");
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudieron actualizar los permisos.");
      return false;
    } finally {
      setBusy(null);
    }
  }

  async function incorporar(event: FormEvent) {
    event.preventDefault();
    if (await guardarRol(identidadId.trim(), rolExistente)) {
      setIdentidadId("");
      setPagina(0);
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
      {esSuperAdmin && (
        <Card>
          <CardHeader title="Asignar acceso a un usuario existente" description="Utiliza el UUID de una identidad ya registrada para asignarle un rol en este condominio. Su estado de cuenta se conserva." />
          <CardBody>
            <form onSubmit={incorporar} className="grid items-end gap-4 sm:grid-cols-3">
              <Field label="UUID del usuario" required><Input value={identidadId} minLength={36} maxLength={36} onChange={(event) => setIdentidadId(event.target.value)} placeholder="UUID de la identidad existente" /></Field>
              <Field label="Rol a asignar" required><Select value={rolExistente} onChange={(event) => setRolExistente(event.target.value as RolContextual)}><option value="ADMIN_JUNTA">Admin / Junta</option><option value="AUDITOR">Auditor</option><option value="RESIDENTE">Residente</option></Select></Field>
              <Button type="submit" disabled={busy !== null}>Asignar rol</Button>
            </form>
          </CardBody>
        </Card>
      )}
      <Card>
        <CardHeader title="Usuarios del condominio" description="La cuenta controla el acceso global; el rol determina los permisos en este condominio. Revocar un rol conserva la identidad y sus vínculos." />
        <CardBody>
          <div className="mb-4 flex items-center justify-between gap-3">
            <p className="text-sm text-muted">{esSuperAdmin ? "Puedes activar o desactivar cuentas. El cambio afecta a todos los condominios de esa persona." : "Solo SuperAdmin puede cambiar el estado de las cuentas."}</p>
            <Button variant="secondary" onClick={actualizar} disabled={loading || busy !== null}>Actualizar</Button>
          </div>
          {loading ? <p role="status">Cargando usuarios…</p> : usuarios.length === 0 ? <p>No hay usuarios en esta página.</p> : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Usuarios y estado de acceso del condominio</caption>
                <thead><tr className="border-b border-line"><th scope="col" className="p-3">Nombre</th><th scope="col" className="p-3">Correo</th><th scope="col" className="p-3">Documento</th><th scope="col" className="p-3">Estado de cuenta</th><th scope="col" className="p-3">Rol y permisos</th>{esSuperAdmin && <th scope="col" className="p-3">Acceso global</th>}</tr></thead>
                <tbody>{usuarios.map((usuario) => (
                  <tr key={usuario.id} className="border-b border-line">
                    <td className="p-3">{usuario.nombre} {usuario.apellido}<span className="mt-1 block max-w-48 break-all text-xs text-muted" title="UUID del usuario">{usuario.id}</span></td><td className="p-3">{usuario.email}</td><td className="p-3">{usuario.documento_identidad}</td>
                    <td className="p-3"><Badge tone={usuario.esta_activo ? "success" : "neutral"}>{usuario.esta_activo ? "Activo" : "Inactivo"}</Badge></td>
                    <td className="p-3"><RolUsuarioEditor usuario={usuario} esSuperAdmin={esSuperAdmin} esPropio={usuario.id === usuarioActualId} disabled={busy !== null} onGuardar={(rol) => void guardarRol(usuario.id, rol)} onRevocar={() => void guardarRol(usuario.id, null)} /></td>
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
