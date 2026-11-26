"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { useAuth } from "@/context/AuthContext";
import {
  ApiError,
  asignarIncidencia,
  listarUsuarios,
  listarProveedores,
  type Proveedor,
  type AsignacionIncidencia,
  type Incidencia,
} from "@/lib/api";

interface Props {
  incidencia: Incidencia;
  onAsignada: (asignacion: AsignacionIncidencia) => void;
}

export function AsignacionIncidenciaForm({ incidencia, onAsignada }: Props) {
  const { user } = useAuth();
  const clave = useRef<string>(crypto.randomUUID());
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [proveedorId, setProveedorId] = useState("");
  const [cargandoProveedores, setCargandoProveedores] = useState(true);
  const [errorProveedores, setErrorProveedores] = useState("");
  const [tipo, setTipo] = useState<"INTERNO" | "PROVEEDOR">("INTERNO");
  const [usuarios, setUsuarios] = useState<{ id: string; nombre: string; email: string }[]>([]);
  const [error, setError] = useState("");
  const [ocupada, setOcupada] = useState(false);

  useEffect(() => {
    if (!user?.condominio_id) return;
    const control = new AbortController();
    listarUsuarios(user.condominio_id, 50, 0)
      .then((lista) => {
        if (!control.signal.aborted) {
          setUsuarios(
            lista
              .filter((cuenta) => cuenta.esta_activo && cuenta.rol_activo)
              .map((cuenta) => ({ id: cuenta.id, nombre: cuenta.nombre, email: cuenta.email })),
          );
        }
      })
      .catch(() => undefined);
    return () => control.abort();
  }, [user?.condominio_id]);

  useEffect(() => {
    if (!user?.condominio_id) return;
    let vigente = true;
    setCargandoProveedores(true);
    setErrorProveedores("");
    setProveedores([]);
    setProveedorId("");
    listarProveedores(user.condominio_id, { activo: true })
      .then((lista) => { if (vigente) setProveedores(lista); })
      .catch(() => { if (vigente) setErrorProveedores("No pudimos cargar el directorio de proveedores."); })
      .finally(() => { if (vigente) setCargandoProveedores(false); });
    return () => { vigente = false; };
  }, [user?.condominio_id]);

  async function guardar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setError("");
    const datos = new FormData(evento.currentTarget);
    const plazoLocal = String(datos.get("plazo") ?? "");
    if (!plazoLocal) {
      setError("Selecciona el plazo de atención.");
      return;
    }
    const plazo = new Date(plazoLocal);
    if (Number.isNaN(plazo.getTime()) || plazo.getTime() <= Date.now()) {
      setError("El plazo debe ser una fecha futura.");
      return;
    }
    const nota = String(datos.get("nota") ?? "").trim();
    const solicitud =
      tipo === "INTERNO"
        ? {
            version: incidencia.version,
            responsable_usuario_id: String(datos.get("responsable") ?? ""),
            plazo: plazo.toISOString(),
            ...(nota ? { nota } : {}),
          }
        : {
            version: incidencia.version,
            responsable_proveedor_id: proveedorId,
            plazo: plazo.toISOString(),
            ...(nota ? { nota } : {}),
          };
    setOcupada(true);
    try {
      onAsignada(await asignarIncidencia(incidencia.id, solicitud, clave.current));
    } catch (causa) {
      setError(causa instanceof ApiError ? causa.message : "No pudimos guardar la asignación.");
    } finally {
      setOcupada(false);
    }
  }

  return (
    <Card>
      <CardHeader
        title="Asignar responsable"
        description="Registra quién atenderá el ticket y el plazo de atención."
      />
      <CardBody>
        {error && <Alert tone="danger">{error}</Alert>}
        <form className="mt-4 space-y-4" onSubmit={guardar}>
          <Field label="Tipo de responsable" required>
            <Select value={tipo} onChange={(evento) => setTipo(evento.target.value as typeof tipo)}>
              <option value="INTERNO">Equipo interno del condominio</option>
              <option value="PROVEEDOR">Proveedor externo</option>
            </Select>
          </Field>
          {tipo === "INTERNO" ? (
            <Field label="Responsable" required>
              <Select name="responsable" defaultValue="">
                <option value="" disabled>Selecciona una persona activa</option>
                {usuarios.map((cuenta) => (
                  <option key={cuenta.id} value={cuenta.id}>
                    {cuenta.nombre} · {cuenta.email}
                  </option>
                ))}
              </Select>
            </Field>
          ) : (
            <>
              <Field label="Proveedor del directorio" required>
                <Select required value={proveedorId}
                  disabled={cargandoProveedores || proveedores.length === 0}
                  onChange={(evento) => setProveedorId(evento.target.value)}>
                  <option value="" disabled>{cargandoProveedores ? "Cargando proveedores…" : "Selecciona un proveedor activo"}</option>
                  {proveedores.map((proveedor) => (
                    <option key={proveedor.id} value={proveedor.id}>
                      {proveedor.nombre_comercial || proveedor.razon_social} · {proveedor.ruc}
                    </option>
                  ))}
                </Select>
              </Field>
              {errorProveedores && <Alert tone="danger">{errorProveedores}</Alert>}
              {!cargandoProveedores && !errorProveedores && proveedores.length === 0 &&
                <p className="text-sm text-muted">Registra un proveedor activo en el directorio antes de asignarlo.</p>}
              {proveedorId && <p className="text-sm text-muted">
                Contacto: {proveedores.find((p) => p.id === proveedorId)?.contacto_email || "Sin correo registrado"}
              </p>}
            </>
          )}
          <Field label="Plazo de atención" required>
            <Input name="plazo" type="datetime-local" />
          </Field>
          <Field label="Nota interna">
            <Textarea name="nota" maxLength={500} rows={2} />
          </Field>
          <Button type="submit" loading={ocupada} loadingText="Guardando…"
            disabled={tipo === "PROVEEDOR" && !proveedorId}>
            Confirmar asignación
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
