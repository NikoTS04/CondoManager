"use client";

import { useState, type FormEvent } from "react";
import { Building2, CircleDollarSign, Info, Save, Settings2 } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { MoneyInput } from "@/components/ui/MoneyInput";
import { EmptyState } from "@/components/ui/Feedback";
import { crearCondominio, type Condominio, type Moneda, type ReglaMoraTipo } from "@/lib/api";
import { isValidMoney } from "@/lib/money";

interface ConfiguracionCondominioProps {
  puedeEditar: boolean;
}

export default function ConfiguracionCondominio({ puedeEditar }: ConfiguracionCondominioProps) {
  const [nombre, setNombre] = useState("Villa Bonita 3");
  const [direccion, setDireccion] = useState("Av. Principal 123, Lima");
  const [moneda, setMoneda] = useState<Moneda>("PEN");
  const [reglaMora, setReglaMora] = useState<ReglaMoraTipo>("MONTO_FIJO");
  const [montoMoraFijo, setMontoMoraFijo] = useState("20.00");
  const [tasaMoraPorcentaje, setTasaMoraPorcentaje] = useState("0.0000");
  const [diaVencimiento, setDiaVencimiento] = useState("20");
  const [diasGracia, setDiasGracia] = useState("2");
  const [error, setError] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);
  const [configuracion, setConfiguracion] = useState<Condominio | null>(null);

  async function guardarConfiguracion(event: FormEvent) {
    event.preventDefault();
    setError(null);

    if (!puedeEditar) {
      setError("Solo un usuario SuperAdmin puede configurar un condominio.");
      return;
    }
    if (!nombre.trim() || !direccion.trim()) {
      setError("El nombre y la dirección del condominio son obligatorios.");
      return;
    }
    if (!/^\d{1,2}$/.test(diaVencimiento)) {
      setError("El día de vencimiento debe ser un entero entre 1 y 28.");
      return;
    }
    if (!/^\d{1,2}$/.test(diasGracia)) {
      setError("Los días de gracia deben ser un entero entre 0 y 30.");
      return;
    }

    const vencimiento = Number.parseInt(diaVencimiento, 10);
    const gracia = Number.parseInt(diasGracia, 10);
    if (vencimiento < 1 || vencimiento > 28) {
      setError("El día de vencimiento debe ser un entero entre 1 y 28.");
      return;
    }
    if (gracia < 0 || gracia > 30) {
      setError("Los días de gracia deben ser un entero entre 0 y 30.");
      return;
    }
    if (reglaMora === "MONTO_FIJO" && !isValidMoney(montoMoraFijo)) {
      setError("Ingresa un monto de mora válido con hasta dos decimales.");
      return;
    }
    if (
      reglaMora === "PORCENTAJE_SALDO" &&
      !/^(100\.0000|\d{1,2}\.\d{4})$/.test(tasaMoraPorcentaje)
    ) {
      setError("La tasa debe estar entre 0.0000 y 100.0000 y tener cuatro decimales.");
      return;
    }

    setGuardando(true);
    try {
      const resultado = await crearCondominio({
        nombre: nombre.trim(),
        direccion: direccion.trim(),
        moneda,
        regla_mora_tipo: reglaMora,
        monto_mora_fijo: reglaMora === "MONTO_FIJO" ? montoMoraFijo : null,
        tasa_mora_porcentaje: reglaMora === "PORCENTAJE_SALDO" ? tasaMoraPorcentaje : null,
        dia_vencimiento: vencimiento,
        dias_gracia: gracia,
      });
      if (!resultado.ok || !resultado.data) {
        setError(resultado.error || "No se pudo guardar la configuración.");
        return;
      }
      setConfiguracion(resultado.data);
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
          title="Configurar un condominio"
          description="Define la identidad, moneda y reglas financieras generales."
          icon={<Settings2 className="h-5 w-5" aria-hidden="true" />}
          actions={<Badge tone="info">Conectado a la API</Badge>}
        />
        <CardBody>
          {!puedeEditar && (
            <div className="mb-4 rounded-lg border border-audit-200 bg-audit-50 p-3">
              <Badge tone="audit">Solo lectura</Badge>
            </div>
          )}
          {error && <Alert tone="danger" title="No se pudo guardar">{error}</Alert>}
          <form onSubmit={guardarConfiguracion} className="mt-4 space-y-5">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Nombre del condominio" required>
                <Input
                  value={nombre}
                  onChange={(event) => setNombre(event.target.value)}
                  disabled={!puedeEditar}
                  autoComplete="organization"
                />
              </Field>
              <Field label="Moneda principal" required>
                <Select
                  value={moneda}
                  onChange={(event) => setMoneda(event.target.value as Moneda)}
                  disabled={!puedeEditar}
                >
                  <option value="PEN">PEN — Sol peruano</option>
                  <option value="USD">USD — Dólar estadounidense</option>
                </Select>
              </Field>
            </div>

            <Field label="Dirección" required>
              <Textarea
                value={direccion}
                onChange={(event) => setDireccion(event.target.value)}
                disabled={!puedeEditar}
                rows={2}
              />
            </Field>

            <section className="rounded-xl border border-line bg-canvas p-4">
              <h3 className="flex items-center gap-2 text-sm font-semibold">
                <CircleDollarSign className="h-4 w-4 text-warning-600" aria-hidden="true" />
                Reglas generales de cobranza
              </h3>
              <div className="mt-4 grid gap-4 md:grid-cols-2">
                <Field label="Regla de mora" required>
                  <Select
                    value={reglaMora}
                    onChange={(event) => setReglaMora(event.target.value as ReglaMoraTipo)}
                    disabled={!puedeEditar}
                  >
                    <option value="MONTO_FIJO">Monto fijo</option>
                    <option value="PORCENTAJE_SALDO">Porcentaje sobre saldo</option>
                  </Select>
                </Field>
                {reglaMora === "MONTO_FIJO" ? (
                  <Field label="Monto fijo de mora" required>
                    <MoneyInput
                      value={montoMoraFijo}
                      onValueChange={setMontoMoraFijo}
                      moneda={moneda}
                      disabled={!puedeEditar}
                    />
                  </Field>
                ) : (
                  <Field label="Tasa de mora (%)" required>
                    <Input
                      inputMode="decimal"
                      value={tasaMoraPorcentaje}
                      onChange={(event) => setTasaMoraPorcentaje(event.target.value)}
                      disabled={!puedeEditar}
                    />
                  </Field>
                )}
                <Field label="Día de vencimiento mensual" required>
                  <Input
                    inputMode="numeric"
                    value={diaVencimiento}
                    onChange={(event) => setDiaVencimiento(event.target.value)}
                    disabled={!puedeEditar}
                  />
                </Field>
                <Field label="Días de gracia" required>
                  <Input
                    inputMode="numeric"
                    value={diasGracia}
                    onChange={(event) => setDiasGracia(event.target.value)}
                    disabled={!puedeEditar}
                  />
                </Field>
              </div>
            </section>

            {puedeEditar && (
              <Button
                type="submit"
                loading={guardando}
                icon={<Save className="h-4 w-4" aria-hidden="true" />}
              >
                Guardar configuración
              </Button>
            )}
          </form>
        </CardBody>
      </Card>

      <aside className="space-y-4">
        <Alert tone="info" title="Persistencia y autorización">
          <span className="inline-flex items-start gap-2">
            <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            El alta se envía al backend con la sesión activa. La autorización también se
            valida en el servidor.
          </span>
        </Alert>
        <Card>
          <CardHeader title="Estado de configuración" />
          <CardBody>
            {configuracion ? (
              <div className="space-y-3 text-sm">
                <Badge tone="success">Condominio activo</Badge>
                <div className="rounded-lg bg-canvas p-4">
                  <p className="font-semibold">{configuracion.nombre}</p>
                  <p className="mt-1 text-muted">{configuracion.direccion}</p>
                  <p className="mt-2">Moneda: {configuracion.moneda}</p>
                  <p>Día de vencimiento: {configuracion.dia_vencimiento}</p>
                  <p>Días de gracia: {configuracion.dias_gracia}</p>
                  <p className="mt-2 break-all font-mono text-xs">UUID: {configuracion.id}</p>
                </div>
              </div>
            ) : (
              <EmptyState
                icon={Building2}
                title="Sin configuración persistida"
                description="Completa el formulario para crear el condominio."
              />
            )}
          </CardBody>
        </Card>
      </aside>
    </div>
  );
}
