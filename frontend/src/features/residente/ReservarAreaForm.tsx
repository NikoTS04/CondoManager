"use client";

import { useState } from "react";
import { PlusCircle, ShieldAlert, ArrowRight } from "lucide-react";
import { Field, Input, Select } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { formatMoney } from "@/lib/money";
import { crearReserva, type AreaComun } from "@/lib/api";

function getTodayLima(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Lima",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

export interface ReservarAreaFormProps {
  areas: AreaComun[];
  condominioId?: string | null;
  departamentoNumero: string;
  estaEnMora: boolean;
  deudaVencida?: string;
  errorAreas?: string | null;
  onRetryAreas?: () => void;
  onSuccess?: () => void;
  onGoToPagos?: () => void;
}

export function ReservarAreaForm({
  areas,
  condominioId,
  departamentoNumero,
  estaEnMora,
  deudaVencida,
  errorAreas,
  onRetryAreas,
  onSuccess,
  onGoToPagos,
}: ReservarAreaFormProps) {
  const [selectedAreaId, setSelectedAreaId] = useState<string>(areas[0]?.id || "");
  const [fechaReserva, setFechaReserva] = useState<string>(getTodayLima());
  const [horaInicio, setHoraInicio] = useState<string>("19:00");
  const [horaFin, setHoraFin] = useState<string>("22:00");
  const [reservaError, setReservaError] = useState<string | null>(null);
  const [reservaSuccess, setReservaSuccess] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  // Asegura área por defecto si la lista se carga después
  const effectiveAreaId = selectedAreaId || areas[0]?.id || "";

  async function handleCrearReserva(e: React.FormEvent) {
    e.preventDefault();
    setReservaError(null);
    setReservaSuccess(null);

    if (estaEnMora) {
      setReservaError("No puedes reservar áreas comunes mientras mantengas cuotas vencidas.");
      return;
    }

    if (!effectiveAreaId) {
      setReservaError("Selecciona un espacio común.");
      return;
    }

    setIsSubmitting(true);
    const res = await crearReserva({
      condominio_id: condominioId || "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      area_id: effectiveAreaId,
      departamento_id: departamentoNumero,
      fecha_reserva: fechaReserva,
      hora_inicio: horaInicio,
      hora_fin: horaFin,
    });

    setIsSubmitting(false);

    if (res.ok) {
      setReservaSuccess("¡Reserva confirmada con éxito! Se ha notificado a tu correo con las normas del espacio.");
      if (onSuccess) onSuccess();
    } else {
      setReservaError(res.error || "No se pudo registrar la reserva. Inténtalo de nuevo.");
    }
  }

  return (
    <Card>
      <CardHeader
        title="Solicitar Turno"
        description="Elige el espacio común y el horario de tu reserva."
        icon={<PlusCircle className="h-5 w-5 text-brand-600" aria-hidden />}
      />

      <CardBody className="space-y-4">
        {errorAreas && (
          <Alert
            tone="danger"
            title="No pudimos cargar los espacios comunes"
            action={
              onRetryAreas ? (
                <Button variant="secondary" size="sm" onClick={onRetryAreas}>
                  Reintentar
                </Button>
              ) : undefined
            }
          >
            {errorAreas}
          </Alert>
        )}

        {reservaError && (
          <Alert tone="danger" title="No pudimos reservar" onDismiss={() => setReservaError(null)}>
            {reservaError}
          </Alert>
        )}

        {reservaSuccess && (
          <Alert tone="success" title="Reserva realizada" onDismiss={() => setReservaSuccess(null)}>
            {reservaSuccess}
          </Alert>
        )}

        <form onSubmit={handleCrearReserva} className="space-y-4">
          <Field label="Espacio Común" required>
            <Select
              value={effectiveAreaId}
              onChange={(e) => setSelectedAreaId(e.target.value)}
              disabled={estaEnMora || areas.length === 0}
            >
              {areas.length === 0 ? (
                <option value="">No hay espacios disponibles</option>
              ) : (
                areas.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.nombre} ({formatMoney(a.costo_reserva, "PEN")})
                  </option>
                ))
              )}
            </Select>
          </Field>

          <Field label="Fecha de Reserva" required>
            <Input
              type="date"
              value={fechaReserva}
              onChange={(e) => setFechaReserva(e.target.value)}
              disabled={estaEnMora}
            />
          </Field>

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Hora Inicio" required>
              <Input
                type="time"
                value={horaInicio}
                onChange={(e) => setHoraInicio(e.target.value)}
                disabled={estaEnMora}
              />
            </Field>

            <Field label="Hora Fin" required>
              <Input
                type="time"
                value={horaFin}
                onChange={(e) => setHoraFin(e.target.value)}
                disabled={estaEnMora}
              />
            </Field>
          </div>

          <div className="pt-2">
            {estaEnMora ? (
              <div className="rounded-xl border border-danger-200 bg-danger-50 p-4 space-y-3">
                <div className="flex items-start gap-2.5">
                  <ShieldAlert className="h-5 w-5 text-danger-600 shrink-0 mt-0.5" aria-hidden />
                  <div className="space-y-1">
                    <p className="text-sm font-semibold text-danger-800">
                      Reserva bloqueada por mora
                    </p>
                    <p className="text-xs text-danger-700 leading-relaxed">
                      Tu departamento registra cuotas pendientes
                      {deudaVencida ? ` por ${formatMoney(deudaVencida, "PEN")}` : ""}. Regulariza tu saldo para habilitar las reservas.
                    </p>
                  </div>
                </div>

                {onGoToPagos && (
                  <Button
                    type="button"
                    variant="primary"
                    fullWidth
                    size="sm"
                    onClick={onGoToPagos}
                    icon={<ArrowRight className="h-4 w-4" aria-hidden />}
                  >
                    Ir a Reportar Pago
                  </Button>
                )}
              </div>
            ) : (
              <Button
                type="submit"
                variant="primary"
                fullWidth
                disabled={areas.length === 0}
                loading={isSubmitting}
                loadingText="Verificando disponibilidad…"
              >
                Confirmar Reserva
              </Button>
            )}
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
