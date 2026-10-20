"use client";

import { useState } from "react";
import { Calendar, Trash2, Users } from "lucide-react";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/Alert";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { SkeletonList, EmptyState } from "@/components/ui/Feedback";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { ReservaStatusChip } from "@/components/domain/ReservaStatusChip";
import { formatDate, formatHora } from "@/lib/format";
import { cancelarReserva, type AreaComun, type Reserva } from "@/lib/api";

export interface MisReservasListProps {
  reservas: Reserva[];
  areas: AreaComun[];
  departamentoNumero: string;
  loading?: boolean;
  error?: string | null;
  errorAreas?: string | null;
  onRetry?: () => void;
  onRetryAreas?: () => void;
  onReservaCancelled?: () => void;
}

export function MisReservasList({
  reservas,
  areas,
  departamentoNumero,
  loading = false,
  error = null,
  errorAreas = null,
  onRetry,
  onRetryAreas,
  onReservaCancelled,
}: MisReservasListProps) {
  const [reservaACancelar, setReservaACancelar] = useState<Reserva | null>(null);
  const [isCancelling, setIsCancelling] = useState(false);
  const [cancelError, setCancelError] = useState<string | null>(null);

  async function handleConfirmCancelar() {
    if (!reservaACancelar) return;
    setIsCancelling(true);
    setCancelError(null);

    const res = await cancelarReserva(reservaACancelar.id);
    setIsCancelling(false);

    if (res.ok) {
      setReservaACancelar(null);
      if (onReservaCancelled) onReservaCancelled();
    } else {
      setCancelError(res.error || "No se pudo cancelar la reserva.");
    }
  }

  return (
    <div className="space-y-6">
      {/* Catálogo de Áreas Comunes Disponibles */}
      <Card>
        <CardHeader
          title="Catálogo de Espacios Disponibles"
          description="Espacios comunes autorizados y tarifas por turno de reserva."
          icon={<Users className="h-5 w-5 text-brand-600" aria-hidden />}
        />
        <CardBody>
          {errorAreas ? (
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
          ) : areas.length === 0 ? (
            <EmptyState
              icon={Users}
              title="No hay áreas comunes disponibles"
              description="No se encontraron áreas comunes activas en este momento."
            />
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {areas.map((area) => (
                <div
                  key={area.id}
                  className="rounded-xl border border-line bg-canvas p-4 transition-colors hover:border-brand-200"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="font-semibold text-ink text-sm">{area.nombre}</h3>
                    <span className="shrink-0 rounded-full bg-brand-50 px-2 py-0.5 text-xs font-bold text-brand-700">
                      <MoneyAmount value={area.costo_reserva} />
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-muted leading-relaxed">
                    {area.descripcion}
                  </p>
                  <div className="mt-3 flex items-center justify-between text-xs text-muted">
                    <span>Aforo máximo: {area.aforo_maximo} personas</span>
                    <span className="font-medium text-success-700">• Habilitado</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>

      {/* Listado de Reservas y Turnos Confirmados */}
      <Card>
        <CardHeader
          title="Calendario y Turnos del Condominio"
          description="Turnos programados para las áreas comunes y opciones de cancelación."
          icon={<Calendar className="h-5 w-5 text-brand-600" aria-hidden />}
        />
        <CardBody className="space-y-4">
          {cancelError && (
            <Alert
              tone="danger"
              title="Error al cancelar"
              onDismiss={() => setCancelError(null)}
            >
              {cancelError}
            </Alert>
          )}

          {loading ? (
            <SkeletonList rows={3} label="Cargando reservas del condominio…" />
          ) : error ? (
            <Alert
              tone="danger"
              title="No pudimos cargar las reservas"
              action={
                onRetry ? (
                  <Button variant="secondary" size="sm" onClick={onRetry}>
                    Reintentar
                  </Button>
                ) : undefined
              }
            >
              {error}
            </Alert>
          ) : reservas.length === 0 ? (
            <EmptyState
              icon={Calendar}
              title="No hay reservas registradas"
              description="Aún no se han programado reservas para los espacios comunes de Villa Bonita 3."
            />
          ) : (
            <div className="divide-y divide-line">
              {reservas.map((r) => {
                const esPropia = r.departamento_id === departamentoNumero;
                return (
                  <div
                    key={r.id}
                    className="py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-sm first:pt-0 last:pb-0"
                  >
                    <div className="space-y-0.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <p className="font-semibold text-ink">
                          {r.area_nombre || "Área Común"} · Dpto. {r.departamento_id}
                        </p>
                        {esPropia && (
                          <span className="rounded-md bg-brand-50 px-1.5 py-0.5 text-[11px] font-semibold text-brand-700">
                            Tu turno
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-muted">
                        {formatDate(r.fecha_reserva)} · {formatHora(r.hora_inicio)} a{" "}
                        {formatHora(r.hora_fin)} · Tarifa:{" "}
                        <MoneyAmount value={r.costo_reserva} className="font-medium" />
                      </p>
                    </div>

                    <div className="flex items-center justify-between sm:justify-end gap-3 shrink-0">
                      <ReservaStatusChip status={r.estado} />

                      {esPropia && r.estado === "CONFIRMADA" && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setReservaACancelar(r)}
                          className="text-danger-600 hover:text-danger-700 hover:bg-danger-50"
                          icon={<Trash2 className="h-4 w-4" aria-hidden />}
                        >
                          Cancelar
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardBody>
      </Card>

      {/* Diálogo de Confirmación para Cancelar Reserva */}
      <ConfirmDialog
        open={reservaACancelar !== null}
        title="Cancelar reserva"
        confirmLabel="Sí, cancelar reserva"
        tone="danger"
        loading={isCancelling}
        onConfirm={handleConfirmCancelar}
        onCancel={() => setReservaACancelar(null)}
      >
        <p>
          ¿Deseas cancelar la reserva de{" "}
          <strong>{reservaACancelar?.area_nombre || "el área común"}</strong> programada
          para el <strong>{formatDate(reservaACancelar?.fecha_reserva)}</strong> de{" "}
          <strong>
            {formatHora(reservaACancelar?.hora_inicio)} a{" "}
            {formatHora(reservaACancelar?.hora_fin)}
          </strong>
          ?
        </p>
        <p className="text-xs text-muted mt-2">
          Esta acción liberará el espacio inmediatamente para que otros residentes puedan reservarlo.
        </p>
      </ConfirmDialog>
    </div>
  );
}
