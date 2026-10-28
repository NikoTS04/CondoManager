"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Building2, CircleDollarSign, Info, Plus, Save, Settings2 } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/Feedback";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { MoneyInput } from "@/components/ui/MoneyInput";
import {
  crearCondominio,
  actualizarPoliticaMora,
  listarCondominios,
  type Condominio,
  type Moneda,
  type ReglaMoraTipo,
} from "@/lib/api";
import { isPositiveMoney, isValidMoney } from "@/lib/money";

interface ConfiguracionCondominioProps {
  puedeEditar: boolean;
  condominioActivoId: string | null;
  onCondominioSeleccionado: (condominioId: string | null) => void;
}

export default function ConfiguracionCondominio({
  puedeEditar,
  condominioActivoId,
  onCondominioSeleccionado,
}: ConfiguracionCondominioProps) {
  const [condominios, setCondominios] = useState<Condominio[]>([]);
  const [configuracion, setConfiguracion] = useState<Condominio | null>(null);
  const [modoCreacion, setModoCreacion] = useState(false);
  const [editandoPolitica, setEditandoPolitica] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [montoMoraDiario, setMontoMoraDiario] = useState("1.00");
  const [cargando, setCargando] = useState(true);
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);

  const [nombre, setNombre] = useState("Villa Bonita 3");
  const [direccion, setDireccion] = useState("Av. Principal 123, Lima");
  const [moneda, setMoneda] = useState<Moneda>("PEN");
  const [reglaMora, setReglaMora] = useState<ReglaMoraTipo>("MONTO_DIARIO");
  const [montoMoraFijo, setMontoMoraFijo] = useState("20.00");
  const [tasaMoraPorcentaje, setTasaMoraPorcentaje] = useState("0.0000");
  const [diaVencimiento, setDiaVencimiento] = useState("10");
  const [diasGracia, setDiasGracia] = useState("0");

  const seleccionar = useCallback((condominio: Condominio) => {
    setConfiguracion(condominio);
    setModoCreacion(false);
    setEditandoPolitica(false);
    setError(null);
    setMensaje(null);
    onCondominioSeleccionado(condominio.id);
  }, [onCondominioSeleccionado]);

  const cargarCondominios = useCallback(async () => {
    setCargando(true);
    setError(null);
    try {
      const resultado = await listarCondominios();
      if (!resultado.ok || !resultado.data) {
        setError(resultado.error || "No se pudieron cargar los condominios existentes.");
        return;
      }

      setCondominios(resultado.data);
      const guardado = resultado.data.find((item) => item.id === condominioActivoId);
      const automatico = guardado || (resultado.data.length === 1 ? resultado.data[0] : null);
      if (automatico) {
        setConfiguracion(automatico);
        setModoCreacion(false);
        if (automatico.id !== condominioActivoId) {
          onCondominioSeleccionado(automatico.id);
        }
        return;
      }

      setConfiguracion(null);
      setModoCreacion(resultado.data.length === 0);
      if (condominioActivoId) onCondominioSeleccionado(null);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "No se pudieron cargar los condominios.");
    } finally {
      setCargando(false);
    }
  }, [condominioActivoId, onCondominioSeleccionado]);

  useEffect(() => {
    void cargarCondominios();
  }, [cargarCondominios]);

  function iniciarCreacion() {
    setEditandoPolitica(false);
    setMontoMoraDiario("1.00");
    setNombre("Villa Bonita 3");
    setDireccion("Av. Principal 123, Lima");
    setMoneda("PEN");
    setReglaMora("MONTO_DIARIO");
    setMontoMoraFijo("20.00");
    setTasaMoraPorcentaje("0.0000");
    setDiaVencimiento("10");
    setDiasGracia("0");
    setError(null);
    setMensaje(null);
    setModoCreacion(true);
  }

  async function guardarConfiguracion(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMensaje(null);

    if (!puedeEditar) {
      setError("Solo un usuario SuperAdmin puede configurar un condominio.");
      return;
    }
    if (!nombre.trim() || !direccion.trim()) {
      setError("El nombre y la dirección del condominio son obligatorios.");
      return;
    }

    const vencimiento = Number(diaVencimiento);
    const gracia = Number(diasGracia);
    if (!Number.isInteger(vencimiento) || vencimiento < 1 || vencimiento > 28) {
      setError("El día de vencimiento debe ser un entero entre 1 y 28.");
      return;
    }
    if (!Number.isInteger(gracia) || gracia < 0 || gracia > 30) {
      setError("Los días de gracia deben ser un entero entre 0 y 30.");
      return;
    }
    if (reglaMora === "MONTO_FIJO" && !isValidMoney(montoMoraFijo)) {
      setError("Ingresa un monto de mora válido con hasta dos decimales.");
      return;
    }
    if (reglaMora === "MONTO_DIARIO" && !isPositiveMoney(montoMoraDiario)) {
      setError("El importe diario debe ser positivo y tener hasta dos decimales.");
      return;
    }
    if (reglaMora === "PORCENTAJE_SALDO" && !/^(100\.0000|\d{1,2}\.\d{4})$/.test(tasaMoraPorcentaje)) {
      setError("La tasa debe estar entre 0.0000 y 100.0000 y tener cuatro decimales.");
      return;
    }

    setGuardando(true);
    try {
      const datos = {
        nombre: nombre.trim(),
        direccion: direccion.trim(),
        moneda,
        regla_mora_tipo: reglaMora,
        monto_mora_fijo: reglaMora === "MONTO_FIJO" ? montoMoraFijo : null,
        monto_mora_diario: reglaMora === "MONTO_DIARIO" ? montoMoraDiario : null,
        tasa_mora_porcentaje: reglaMora === "PORCENTAJE_SALDO" ? tasaMoraPorcentaje : null,
        dia_vencimiento: vencimiento,
        dias_gracia: gracia,
      };
      const resultado = editandoPolitica && configuracion
        ? await actualizarPoliticaMora(configuracion, datos, motivo)
        : await crearCondominio(datos);
      if (!resultado.ok || !resultado.data) {
        setError(resultado.error || "No se pudo guardar la configuración.");
        return;
      }

      const creado = resultado.data;
      setCondominios((actuales) => [creado, ...actuales.filter((item) => item.id !== creado.id)]);
      seleccionar(creado);
      setMensaje(editandoPolitica ? "Política actualizada. No se modificaron cuotas históricas." : "Condominio creado y seleccionado como contexto activo.");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "No se pudo guardar la configuración.");
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.5fr)_minmax(16rem,0.8fr)]">
      <Card>
        <CardHeader
          title="Contexto del condominio"
          description="Selecciona un condominio existente o registra uno nuevo de forma explícita."
          icon={<Settings2 className="h-5 w-5" aria-hidden="true" />}
          actions={<Badge tone="info">Conectado a la API</Badge>}
        />
        <CardBody className="space-y-5">
          {error && <Alert tone="danger" title="No se pudo completar la operación">{error}</Alert>}
          {mensaje && <Alert tone="success" title="Configuración actualizada">{mensaje}</Alert>}

          <div className="rounded-xl border border-line bg-canvas p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
              <Field label="Condominio activo" className="flex-1">
                <Select
                  value={configuracion?.id || ""}
                  onChange={(event) => {
                    const elegido = condominios.find((item) => item.id === event.target.value);
                    if (elegido) seleccionar(elegido);
                    else {
                      setConfiguracion(null);
                      onCondominioSeleccionado(null);
                    }
                  }}
                  disabled={cargando}
                >
                  <option value="">
                    {cargando
                      ? "Cargando condominios..."
                      : condominios.length > 1
                        ? "Seleccione un condominio"
                        : "Sin condominios disponibles"}
                  </option>
                  {condominios.map((condominio) => (
                    <option key={condominio.id} value={condominio.id}>
                      {condominio.nombre} — {condominio.direccion}
                    </option>
                  ))}
                </Select>
              </Field>
              {puedeEditar && !modoCreacion && (
                <Button type="button" variant="secondary" onClick={iniciarCreacion} icon={<Plus className="h-4 w-4" aria-hidden="true" />}>
                  Nuevo condominio
                </Button>
              )}
            </div>
          </div>

          {modoCreacion && (
            <form onSubmit={guardarConfiguracion} className="space-y-5">
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-semibold">{editandoPolitica ? "Editar política de mora" : "Registrar nuevo condominio"}</h3>
                {condominios.length > 0 && (
                  <Button type="button" variant="ghost" onClick={() => setModoCreacion(false)}>Cancelar</Button>
                )}
              </div>

              <div className="grid gap-4 md:grid-cols-2">
                <Field label="Nombre del condominio" required>
                  <Input disabled={editandoPolitica} value={nombre} onChange={(event) => setNombre(event.target.value)} />
                </Field>
                <Field label="Moneda principal" required>
                  <Select disabled={editandoPolitica} value={moneda} onChange={(event) => setMoneda(event.target.value as Moneda)}>
                    <option value="PEN">PEN — Sol peruano</option>
                    <option value="USD">USD — Dólar estadounidense</option>
                  </Select>
                </Field>
              </div>

              <Field label="Dirección" required>
                <Textarea disabled={editandoPolitica} value={direccion} onChange={(event) => setDireccion(event.target.value)} rows={2} />
              </Field>

              <section className="rounded-xl border border-line bg-canvas p-4">
                <h3 className="flex items-center gap-2 text-sm font-semibold">
                  <CircleDollarSign className="h-4 w-4 text-warning-600" aria-hidden="true" />
                  Reglas generales de cobranza
                </h3>
                <div className="mt-4 grid gap-4 md:grid-cols-2">
                  <Field label="Regla de mora" required>
                    <Select value={reglaMora} onChange={(event) => setReglaMora(event.target.value as ReglaMoraTipo)}>
                      <option value="MONTO_FIJO">Monto fijo</option>
                      <option value="MONTO_DIARIO">Importe diario por cuota vencida</option>
                      <option value="PORCENTAJE_SALDO">Porcentaje sobre saldo</option>
                    </Select>
                  </Field>
                  {reglaMora === "MONTO_DIARIO" ? (
                    <Field label="Importe diario por cuota vencida" required>
                      <MoneyInput value={montoMoraDiario} onValueChange={setMontoMoraDiario} moneda={moneda} />
                    </Field>
                  ) : reglaMora === "MONTO_FIJO" ? (
                    <Field label="Monto fijo de mora" required>
                      <MoneyInput value={montoMoraFijo} onValueChange={setMontoMoraFijo} moneda={moneda} />
                    </Field>
                  ) : (
                    <Field label="Tasa de mora (%)" required>
                      <Input inputMode="decimal" value={tasaMoraPorcentaje} onChange={(event) => setTasaMoraPorcentaje(event.target.value)} />
                    </Field>
                  )}
                  <Field label="Día de vencimiento mensual" required>
                    <Input inputMode="numeric" value={diaVencimiento} onChange={(event) => setDiaVencimiento(event.target.value)} />
                  </Field>
                  <Field label="Días de gracia" required>
                    <Input inputMode="numeric" value={diasGracia} onChange={(event) => setDiasGracia(event.target.value)} />
                  </Field>
                </div>
              </section>

              {editandoPolitica && <Field label="Motivo del cambio" required><Textarea required value={motivo} onChange={(event) => setMotivo(event.target.value)} /></Field>}
              <Alert tone="warning" title="Configuración preparada">El motor persistente de mora diaria está pendiente de integración. Guardar esta política no genera recargos ni recalcula cuotas anteriores.</Alert>

              <Button type="submit" loading={guardando} icon={<Save className="h-4 w-4" aria-hidden="true" />}>
                Guardar configuración
              </Button>
            </form>
          )}
        </CardBody>
      </Card>

      <aside className="space-y-4">
        <Alert tone="info" title="Persistencia y autorización">
          <span className="inline-flex items-start gap-2">
            <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            La selección se conserva para la sesión del SuperAdmin. La autorización también se valida en el servidor.
          </span>
        </Alert>
        <Card>
          <CardHeader title="Condominio seleccionado" />
          <CardBody>
            {configuracion ? (
              <div className="space-y-3 text-sm">
                <Badge tone="success">Contexto activo</Badge>
                <div className="rounded-lg bg-canvas p-4">
                  <p className="font-semibold">{configuracion.nombre}</p>
                  <p className="mt-1 text-muted">{configuracion.direccion}</p>
                  <p className="mt-2">Moneda: {configuracion.moneda}</p>
                  <p>Día de vencimiento: {configuracion.dia_vencimiento}</p>
                  <p>Días de gracia: {configuracion.dias_gracia}</p>
                  {configuracion.monto_mora_diario && <p>Mora diaria por cuota: {configuracion.monto_mora_diario} {configuracion.moneda}</p>}
                  {puedeEditar && <Button size="sm" variant="secondary" onClick={() => {
                    setEditandoPolitica(true); setModoCreacion(true); setMotivo("");
                    setNombre(configuracion.nombre); setDireccion(configuracion.direccion); setMoneda(configuracion.moneda);
                    setReglaMora(configuracion.regla_mora_tipo); setMontoMoraDiario(configuracion.monto_mora_diario || "1.00");
                    setMontoMoraFijo(configuracion.monto_mora_fijo || "0.00"); setTasaMoraPorcentaje(configuracion.tasa_mora_porcentaje || "0.0000");
                    setDiaVencimiento(String(configuracion.dia_vencimiento)); setDiasGracia(String(configuracion.dias_gracia));
                  }}>Editar política</Button>}
                  <p className="mt-2 break-all font-mono text-xs">UUID: {configuracion.id}</p>
                </div>
              </div>
            ) : (
              <EmptyState
                icon={Building2}
                title="Sin condominio seleccionado"
                description={condominios.length > 1
                  ? "Selecciona el condominio con el que deseas trabajar."
                  : "Completa el formulario para crear el primer condominio."}
              />
            )}
          </CardBody>
        </Card>
      </aside>
    </div>
  );
}
