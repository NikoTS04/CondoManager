"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Select } from "@/components/ui/Field";
import {
  asignarVinculoUsuario, listarDepartamentos, listarEdificios, listarVinculosUsuario, revocarVinculoUsuario,
  type CuentaUsuarioConRol, type DepartamentoRegistrado, type Edificio, type VinculoUsuario,
} from "@/lib/api";
import type { TipoRelacion } from "@/lib/session";

const RELACIONES: Record<TipoRelacion, string> = {
  PROPIETARIO_TITULAR: "Propietario titular", COPROPIETARIO: "Copropietario", INQUILINO: "Inquilino",
};

interface Props {
  condominioId: string;
  usuario: CuentaUsuarioConRol;
  onCerrar: () => void;
}

export function VinculosUsuarioSection({ condominioId, usuario, onCerrar }: Props) {
  const [vinculos, setVinculos] = useState<VinculoUsuario[]>([]);
  const [departamentos, setDepartamentos] = useState<DepartamentoRegistrado[]>([]);
  const [edificios, setEdificios] = useState<Edificio[]>([]);
  const [departamentoId, setDepartamentoId] = useState("");
  const [relacion, setRelacion] = useState<TipoRelacion>("PROPIETARIO_TITULAR");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const form = useRef<HTMLFormElement>(null);
  const section = useRef<HTMLDivElement>(null);
  const puedeAsignar = usuario.rol_activo && usuario.rol !== "SUPERADMIN";

  useEffect(() => { section.current?.scrollIntoView({ behavior: "smooth", block: "start" }); }, []);

  useEffect(() => {
    let vigente = true;
    setLoading(true);
    setError(null);
    Promise.all([
      listarVinculosUsuario(condominioId, usuario.id),
      listarDepartamentos(condominioId), listarEdificios(condominioId),
    ])
      .then(([relaciones, unidades, bloques]) => {
        if (!vigente) return;
        setVinculos(relaciones);
        setDepartamentos(unidades);
        setEdificios(bloques);
      })
      .catch((cause) => { if (vigente) setError(cause instanceof Error ? cause.message : "No se pudieron cargar los vínculos."); })
      .finally(() => { if (vigente) setLoading(false); });
    return () => { vigente = false; };
  }, [condominioId, usuario.id, revision]);

  async function guardar(did: string, tipo: TipoRelacion | null) {
    if (busy) return;
    setBusy(true);
    setError(null);
    setMensaje(null);
    try {
      const nuevo = tipo === null
        ? await revocarVinculoUsuario(condominioId, usuario.id, did)
        : await asignarVinculoUsuario(condominioId, usuario.id, did, tipo);
      setVinculos((actuales) => [...actuales.filter((item) => item.id !== nuevo.id), nuevo]
        .sort((a, b) => `${a.edificio_nombre}:${a.numero}`.localeCompare(`${b.edificio_nombre}:${b.numero}`)));
      setDepartamentoId("");
      setMensaje(tipo === null
        ? "Vínculo desactivado. Se conserva el historial y las sesiones anteriores han sido invalidadas."
        : "Vínculo guardado. Los cambios de tenencia requieren que el usuario inicie sesión nuevamente.");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo guardar el vínculo.");
    } finally {
      setBusy(false);
    }
  }

  function editar(vinculo: VinculoUsuario) {
    setDepartamentoId(vinculo.departamento_id);
    setRelacion(vinculo.tipo_relacion);
    form.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  function enviar(event: FormEvent) {
    event.preventDefault();
    if (departamentoId && puedeAsignar) void guardar(departamentoId, relacion);
  }

  return (
    <div ref={section}><Card>
      <CardHeader title={`Departamentos de ${usuario.nombre} ${usuario.apellido}`}
        description="El primer vínculo de una unidad debe ser de propietario titular. Para retirar al último titular, registra primero un reemplazo."
        actions={<Button variant="ghost" onClick={onCerrar}>Cerrar vínculos</Button>} />
      <CardBody className="space-y-5">
        {error && <Alert tone="danger" title="No se completó la vinculación">{error}</Alert>}
        {mensaje && <Alert tone="success" title="Resultado del vínculo">{mensaje}</Alert>}
        {!puedeAsignar && <Alert tone="info">Asigna un rol contextual vigente al usuario para crear o restaurar vínculos. Puedes retirar vínculos existentes respetando la regla del titular.</Alert>}
        {!usuario.esta_activo && <Alert tone="info">La cuenta está inactiva. Registrar tenencia no habilita su inicio de sesión.</Alert>}
        <Button variant="secondary" disabled={busy || loading} onClick={() => setRevision((value) => value + 1)}>Actualizar vínculos</Button>
        {loading ? <p role="status">Cargando vínculos y unidades…</p> : (
          <>
            <form ref={form} onSubmit={enviar} className="grid items-end gap-4 sm:grid-cols-3">
              <Field label="Departamento a vincular" required>
                <Select value={departamentoId} disabled={busy || !puedeAsignar} onChange={(event) => setDepartamentoId(event.target.value)}>
                  <option value="">Selecciona una unidad</option>
                  {departamentos.filter((d) => d.activo).map((d) => <option key={d.id} value={d.id}>{edificios.find((e) => e.id === d.edificio_id)?.nombre_bloque ?? "Edificio"} · Dpto. {d.numero}</option>)}
                </Select>
              </Field>
              <Field label="Relación de tenencia" required><Select value={relacion} disabled={busy || !puedeAsignar} onChange={(event) => setRelacion(event.target.value as TipoRelacion)}>{Object.entries(RELACIONES).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</Select></Field>
              <Button type="submit" disabled={busy || !puedeAsignar || !departamentoId} loading={busy}>Guardar vínculo</Button>
            </form>
            {departamentos.length === 0 && <Alert tone="info">Primero registra departamentos en la sección Estructura.</Alert>}
            {vinculos.length === 0 ? <p>No hay departamentos vinculados a este usuario en el condominio.</p> : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <caption className="sr-only">Vínculos de departamentos del usuario seleccionado</caption>
                  <thead><tr className="border-b border-line"><th scope="col" className="p-3">Departamento</th><th scope="col" className="p-3">Relación</th><th scope="col" className="p-3">Estado del vínculo</th><th scope="col" className="p-3">Acciones</th></tr></thead>
                  <tbody>{vinculos.map((vinculo) => (
                    <tr key={vinculo.id} className="border-b border-line">
                      <td className="p-3">{vinculo.edificio_nombre} · {vinculo.numero}{!vinculo.departamento_activo && <p className="text-xs text-muted">Unidad inactiva</p>}</td>
                      <td className="p-3">{RELACIONES[vinculo.tipo_relacion]}</td>
                      <td className="p-3"><Badge tone={vinculo.es_activo ? "success" : "neutral"}>{vinculo.es_activo ? "Vínculo activo" : "Vínculo inactivo"}</Badge></td>
                      <td className="p-3"><div className="flex flex-wrap gap-2">
                        <Button variant="secondary" size="sm" disabled={busy || !puedeAsignar || !vinculo.departamento_activo} onClick={() => editar(vinculo)} aria-label={`Editar vínculo de ${vinculo.edificio_nombre} ${vinculo.numero}`}>Editar relación</Button>
                        {vinculo.es_activo
                          ? <Button variant="ghost" size="sm" disabled={busy} onClick={() => void guardar(vinculo.departamento_id, null)} aria-label={`Desactivar vínculo de ${vinculo.edificio_nombre} ${vinculo.numero}`}>Desactivar vínculo</Button>
                          : <Button variant="secondary" size="sm" disabled={busy || !puedeAsignar || !vinculo.departamento_activo} onClick={() => void guardar(vinculo.departamento_id, vinculo.tipo_relacion)} aria-label={`Restaurar vínculo de ${vinculo.edificio_nombre} ${vinculo.numero}`}>Restaurar vínculo</Button>}
                      </div></td>
                    </tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </>
        )}
      </CardBody>
    </Card></div>
  );
}
