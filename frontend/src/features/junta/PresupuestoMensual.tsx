"use client";

import { useState, type FormEvent } from "react";
import { CalendarDays, CheckCircle2, ClipboardCheck, Info, Save } from "lucide-react";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { Field, Input, Select } from "@/components/ui/Field";
import { MoneyInput } from "@/components/ui/MoneyInput";
import { isPositiveMoney, normalizeMoney, type Moneda } from "@/lib/money";
import { formatPeriodo } from "@/lib/format";

export interface PresupuestoAprobado {
  condominioId: string;
  periodo: string;
  moneda: Moneda;
  montoTotal: string;
  fechaVencimiento: string;
  estado: "APROBADO";
}

interface PresupuestoMensualProps {
  condominioId: string;
  puedeEditar: boolean;
  onAprobar: (presupuesto: PresupuestoAprobado) => void;
}

export function PresupuestoMensual({
  condominioId,
  puedeEditar,
  onAprobar,
}: PresupuestoMensualProps) {
  const [periodo, setPeriodo] = useState("2026-11");
  const [moneda, setMoneda] = useState<Moneda>("PEN");
  const [montoTotal, setMontoTotal] = useState("");
  const [fechaVencimiento, setFechaVencimiento] = useState("2026-11-20");
  const [estado, setEstado] = useState<"SIN_REGISTRAR" | "BORRADOR" | "APROBADO">("SIN_REGISTRAR");
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmarAprobacion, setConfirmarAprobacion] = useState(false);

  function crearPresupuesto(): PresupuestoAprobado | null {
    if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(periodo)) {
      setError("El periodo debe utilizar el formato AAAA-MM.");
      return null;
    }
    if (!isPositiveMoney(montoTotal)) {
      setError("El monto total debe ser válido y mayor que cero.");
      return null;
    }
    if (!fechaVencimiento || !fechaVencimiento.startsWith(periodo)) {
      setError("La fecha de vencimiento debe pertenecer al periodo seleccionado.");
      return null;
    }

    return {
      condominioId,
      periodo,
      moneda,
      montoTotal: normalizeMoney(montoTotal),
      fechaVencimiento,
      estado: "APROBADO",
    };
  }

  function guardarBorrador() {
    setError(null);
    setMensaje(null);
    if (!puedeEditar) return;
    if (!crearPresupuesto()) return;
    setEstado("BORRADOR");
    setMensaje("Borrador validado localmente. Todavía no habilita la emisión de cuotas.");
  }

  function solicitarAprobacion(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMensaje(null);
    if (!puedeEditar) return;
    if (!crearPresupuesto()) return;
    setConfirmarAprobacion(true);
  }

  function aprobar() {
    const presupuesto = crearPresupuesto();
    if (!presupuesto) return;
    setEstado("APROBADO");
    setMensaje("Presupuesto aprobado en la demostración frontend. La emisión quedó habilitada.");
    onAprobar(presupuesto);
    setConfirmarAprobacion(false);
  }

  return (
    <div className="grid gap-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(17rem,0.85fr)]">
      <Card>
        <CardHeader
          title="Registrar presupuesto mensual"
          description="El presupuesto debe aprobarse antes de emitir las cuotas del periodo."
          icon={<ClipboardCheck className="h-5 w-5" aria-hidden="true" />}
          actions={<Badge tone="info">Demostración frontend</Badge>}
        />
        <CardBody>
          {error && <Alert tone="danger" title="Revisa los datos">{error}</Alert>}
          {mensaje && <Alert tone="success" title="Estado del presupuesto">{mensaje}</Alert>}
          {!puedeEditar && (
            <div className="mb-4 rounded-lg border border-audit-200 bg-audit-50 p-3">
              <Badge tone="audit">Solo lectura</Badge>
              <p className="mt-2 text-sm text-audit-800">
                Los controles para modificar o aprobar el presupuesto no están disponibles.
              </p>
            </div>
          )}

          <form onSubmit={solicitarAprobacion} className="mt-4 space-y-5">
            <div className="grid gap-4 md:grid-cols-2">
              <Field label="Condominio">
                <Input value="Villa Bonita 3" readOnly />
              </Field>
              {puedeEditar ? (
                <Field label="Periodo" required>
                  <Input
                    type="month"
                    value={periodo}
                    onChange={(event) => {
                      setPeriodo(event.target.value);
                      setFechaVencimiento(`${event.target.value}-20`);
                    }}
                  />
                </Field>
              ) : (
                <div>
                  <p className="text-sm font-medium">Periodo</p>
                  <p className="mt-2">{formatPeriodo(periodo)}</p>
                </div>
              )}
              {puedeEditar ? (
                <Field label="Moneda" required>
                  <Select
                    value={moneda}
                    onChange={(event) => setMoneda(event.target.value as Moneda)}
                  >
                    <option value="PEN">PEN — Sol peruano</option>
                    <option value="USD">USD — Dólar estadounidense</option>
                  </Select>
                </Field>
              ) : (
                <div>
                  <p className="text-sm font-medium">Moneda</p>
                  <p className="mt-2">{moneda}</p>
                </div>
              )}
              {puedeEditar ? (
                <Field label="Monto total" required>
                  <MoneyInput
                    value={montoTotal}
                    onValueChange={setMontoTotal}
                    moneda={moneda}
                  />
                </Field>
              ) : (
                <div>
                  <p className="text-sm font-medium">Monto total</p>
                  <p className="mt-2">
                    {montoTotal
                      ? <MoneyAmount value={montoTotal} moneda={moneda} />
                      : "Sin registrar"}
                  </p>
                </div>
              )}
            </div>

            {puedeEditar && (
              <Field label="Fecha de vencimiento" required>
                <Input
                  type="date"
                  value={fechaVencimiento}
                  onChange={(event) => setFechaVencimiento(event.target.value)}
                />
              </Field>
            )}

            {puedeEditar && (
              <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={guardarBorrador}
                  icon={<Save className="h-4 w-4" aria-hidden="true" />}
                >
                  Guardar borrador
                </Button>
                <Button
                  type="submit"
                  icon={<CheckCircle2 className="h-4 w-4" aria-hidden="true" />}
                >
                  Aprobar presupuesto
                </Button>
              </div>
            )}
          </form>
        </CardBody>
      </Card>

      <aside className="space-y-4">
        <Card>
          <CardHeader title="Estado del periodo" />
          <CardBody className="space-y-4">
            <div className="flex items-center gap-3">
              <CalendarDays className="h-6 w-6 text-info-600" aria-hidden="true" />
              <div>
                <p className="font-semibold">{formatPeriodo(periodo)}</p>
                <p className="text-sm text-muted">Estado: {estado.replace("_", " ")}</p>
              </div>
            </div>
            <div className="rounded-lg bg-canvas p-4 text-sm">
              <p>
                Monto: {montoTotal
                  ? <MoneyAmount value={montoTotal} moneda={moneda} />
                  : "Sin registrar"}
              </p>
              <p className="mt-1">Vencimiento: {fechaVencimiento || "Sin definir"}</p>
            </div>
          </CardBody>
        </Card>
        <Alert tone="info" title="Persistencia del presupuesto">
          <span className="inline-flex items-start gap-2">
            <Info className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            La aprobación de esta pantalla es una demostración frontend; no registra aún
            el presupuesto en el backend.
          </span>
        </Alert>
      </aside>

      <ConfirmDialog
        open={confirmarAprobacion}
        title="Aprobar presupuesto"
        confirmLabel="Aprobar presupuesto"
        onCancel={() => setConfirmarAprobacion(false)}
        onConfirm={aprobar}
      >
        <p>
          Se aprobará el presupuesto de {formatPeriodo(periodo)} por{" "}
          {montoTotal && <MoneyAmount value={montoTotal} moneda={moneda} />}.
        </p>
        <p>Este presupuesto habilitará la distribución y emisión de cuotas del periodo.</p>
      </ConfirmDialog>
    </div>
  );
}

export default PresupuestoMensual;
