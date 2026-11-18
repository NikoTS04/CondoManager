"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input, Select } from "@/components/ui/Field";
import { listarVinculosUsuario, relevarAcceso, type CuentaUsuarioConRol, type RelevoAcceso, type VinculoUsuario } from "@/lib/api";
import { UUID_PATTERN } from "@/lib/session";

interface Props {
  condominioId: string; esSuperAdmin: boolean; usuarios: CuentaUsuarioConRol[];
  usuarioActualId: string; onCambio: () => void;
}

export function RelevosSection({ condominioId, esSuperAdmin, usuarios, usuarioActualId, onCambio }: Props) {
  const [tipo, setTipo] = useState<"INQUILINO" | "JUNTA">("INQUILINO");
  const [saliente, setSaliente] = useState("");
  const [entrante, setEntrante] = useState("");
  const [departamento, setDepartamento] = useState("");
  const [rolSaliente, setRolSaliente] = useState("RESIDENTE");
  const [vinculos, setVinculos] = useState<VinculoUsuario[]>([]);
  const [cargando, setCargando] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const operacion = useRef({ huella: "", clave: "" });

  useEffect(() => {
    let vigente = true;
    setVinculos([]);
    setDepartamento("");
    setCargando(false);
    if (!UUID_PATTERN.test(saliente) || tipo !== "INQUILINO") return;
    setCargando(true);
    listarVinculosUsuario(condominioId, saliente)
      .then((data) => { if (vigente) setVinculos(data.filter((v) => v.es_activo && v.departamento_activo && v.tipo_relacion === "INQUILINO")); })
      .catch((cause) => { if (vigente) setError(cause instanceof Error ? cause.message : "No se pudieron cargar las unidades."); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, [saliente, tipo, condominioId]);

  async function enviar(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const datos: RelevoAcceso = { tipo, saliente_id: saliente, entrante_id: entrante };
    if (tipo === "INQUILINO") datos.departamento_id = departamento;
    else datos.rol_saliente = rolSaliente === "REVOCADO" ? null : rolSaliente as "RESIDENTE" | "AUDITOR";
    const huella = JSON.stringify(datos);
    if (operacion.current.huella !== huella) operacion.current = { huella, clave: crypto.randomUUID() };
    setBusy(true); setError(null); setMensaje(null);
    try {
      await relevarAcceso(condominioId, datos, operacion.current.clave);
      setMensaje("Relevo confirmado. Los accesos cambiaron y los avisos quedaron encolados. Se conserva el historial.");
      operacion.current = { huella: "", clave: "" };
      setSaliente(""); setEntrante(""); setDepartamento(""); onCambio();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo completar el relevo. Puedes reintentar."); }
    finally { setBusy(false); }
  }

  const disponibles = usuarios.filter((u) => u.id !== usuarioActualId && !u.es_superadmin);
  return <Card>
    <CardHeader title="Relevar accesos" description="El acceso saliente y el entrante cambian juntos. Las cuentas globales y los demás vínculos se conservan." />
    <CardBody className="space-y-4">
      {error && <Alert tone="danger">{error}</Alert>}
      {mensaje && <Alert tone="success">{mensaje}</Alert>}
      <form onSubmit={enviar} className="grid items-end gap-4 sm:grid-cols-2">
        <Field label="Tipo de relevo" required><Select disabled={busy} value={tipo} onChange={(e) => { setTipo(e.target.value as typeof tipo); setSaliente(""); }}><option value="INQUILINO">Inquilino</option>{esSuperAdmin && <option value="JUNTA">Junta directiva</option>}</Select></Field>
        <Field label="Usuario saliente" required hint="Selecciona una sugerencia o pega el UUID del listado."><Input required list="relevo-salientes" disabled={busy} value={saliente} minLength={36} maxLength={36} onChange={(e) => setSaliente(e.target.value.trim())} placeholder="UUID del usuario saliente" /></Field>
        <datalist id="relevo-salientes">{disponibles.filter((u) => tipo === "INQUILINO" || (u.rol === "ADMIN_JUNTA" && u.rol_activo)).map((u) => <option key={u.id} value={u.id}>{u.nombre} {u.apellido} · {u.email}</option>)}</datalist>
        <Field label="Usuario entrante" required hint="Puedes pegar el UUID de un usuario de otra página del listado."><Input required list="relevo-entrantes" disabled={busy} value={entrante} minLength={36} maxLength={36} onChange={(e) => setEntrante(e.target.value.trim())} placeholder="UUID del usuario entrante" /></Field>
        <datalist id="relevo-entrantes">{disponibles.filter((u) => u.id !== saliente && u.rol_activo).map((u) => <option key={u.id} value={u.id}>{u.nombre} {u.apellido} · {u.email}</option>)}</datalist>
        {tipo === "INQUILINO" ? <Field label="Unidad del inquilino" required><Select required disabled={busy || cargando} value={departamento} onChange={(e) => setDepartamento(e.target.value)}><option value="">{cargando ? "Cargando unidades…" : "Selecciona una unidad"}</option>{vinculos.map((v) => <option key={v.id} value={v.departamento_id}>{v.edificio_nombre} · {v.numero}</option>)}</Select></Field> : <Field label="Acceso final del saliente" required><Select disabled={busy} value={rolSaliente} onChange={(e) => setRolSaliente(e.target.value)}><option value="RESIDENTE">Residente</option><option value="AUDITOR">Auditor</option><option value="REVOCADO">Sin acceso a este condominio</option></Select></Field>}
        <p className="text-xs text-muted sm:col-span-2">Las sugerencias corresponden a la página actual; los UUID pegados se validan en el condominio. Si el entrante es nuevo, invítalo y asígnale acceso antes del relevo. Al retirar al responsable de pago, su designación queda vacía hasta que se configure otra.</p>
        <Button type="submit" loading={busy} disabled={busy || !UUID_PATTERN.test(saliente) || !UUID_PATTERN.test(entrante) || saliente === entrante || (tipo === "INQUILINO" && !departamento)}>Confirmar relevo</Button>
      </form>
    </CardBody>
  </Card>;
}
