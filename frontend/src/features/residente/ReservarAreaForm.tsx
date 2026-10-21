"use client";

import { useEffect, useRef, useState } from "react";
import { PlusCircle, ShieldAlert, ArrowRight } from "lucide-react";
import { Field, Input, Select } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { Spinner } from "@/components/ui/Feedback";
import { formatMoney } from "@/lib/money";
import { crearReserva, fetchDisponibilidad, type AreaComun, type HorarioOcupado } from "@/lib/api";

function getTodayLima(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Lima",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

function minutos(hora: string): number {
  const [h, m] = hora.split(":").map(Number);
  return h * 60 + m;
}

function horaLocal(valor: number): string {
  return `${String(Math.floor(valor / 60)).padStart(2, "0")}:${String(valor % 60).padStart(2, "0")}`;
}

function inicioEnFuturo(fecha: string, hora: string): boolean {
  return new Date(`${fecha}T${hora}:00-05:00`).getTime() > Date.now();
}

export interface ReservarAreaFormProps {
  areas: AreaComun[];
  condominioId?: string | null;
  departamentoId: string;
  estaEnMora: boolean;
  deudaVencida?: string;
  errorAreas?: string | null;
  onRetryAreas?: () => void;
  revisionDisponibilidad?: number;
  onSuccess?: () => void;
  onGoToPagos?: () => void;
}

export function ReservarAreaForm({
  areas,
  condominioId,
  departamentoId,
  estaEnMora,
  deudaVencida,
  errorAreas,
  onRetryAreas,
  revisionDisponibilidad = 0,
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
  const [consultaDisponibilidad, setConsultaDisponibilidad] = useState<{
    clave: string;
    ocupados: HorarioOcupado[];
    error: string | null;
    cargando: boolean;
  }>({ clave: "", ocupados: [], error: null, cargando: false });
  const [revisionCalendario, setRevisionCalendario] = useState(0);

  // Asegura área por defecto si la lista se carga después
  const effectiveAreaId = areas.some((area) => area.id === selectedAreaId) ? selectedAreaId : areas[0]?.id || "";
  const seleccionada = areas.find((area) => area.id === effectiveAreaId);
  const apertura = seleccionada?.hora_apertura ?? "00:00";
  const cierre = seleccionada?.hora_cierre ?? "23:59";
  const duracionMaxima = seleccionada?.tiempo_maximo_horas ?? 24;
  const claveConsulta = `${effectiveAreaId}:${fechaReserva}:${apertura}:${cierre}:${revisionCalendario}:${revisionDisponibilidad}`;
  const consultaVigente = consultaDisponibilidad.clave === claveConsulta && !consultaDisponibilidad.cargando;
  const cargandoDisponibilidad = Boolean(effectiveAreaId && fechaReserva && !consultaVigente);
  const ocupados = consultaVigente ? consultaDisponibilidad.ocupados : [];
  const errorDisponibilidad = consultaVigente ? consultaDisponibilidad.error : null;
  const turnoOcupado = ocupados.some((h) =>
    minutos(horaInicio) < minutos(h.hora_fin) && minutos(horaFin) > minutos(h.hora_inicio));
  const horarioActual = useRef({ inicio: horaInicio, fin: horaFin });
  horarioActual.current = { inicio: horaInicio, fin: horaFin };

  useEffect(() => {
    if (!effectiveAreaId) return;
    const { inicio, fin } = horarioActual.current;
    if (inicio >= apertura && fin <= cierre && fin > inicio && minutos(fin) - minutos(inicio) <= duracionMaxima * 60) return;
    setHoraInicio(apertura);
    setHoraFin(horaLocal(Math.min(minutos(cierre), minutos(apertura) + Math.min(120, duracionMaxima * 60))));
  }, [effectiveAreaId, apertura, cierre, duracionMaxima]);

  useEffect(() => {
    let cancelled = false;
    if (effectiveAreaId && fechaReserva) {
      setConsultaDisponibilidad({ clave: claveConsulta, ocupados: [], error: null, cargando: true });
      void fetchDisponibilidad(effectiveAreaId, fechaReserva)
        .then((data) => {
          if (!cancelled) setConsultaDisponibilidad({ clave: claveConsulta, ocupados: data, error: null, cargando: false });
        })
        .catch((error: unknown) => {
          if (!cancelled) setConsultaDisponibilidad({
            clave: claveConsulta,
            ocupados: [],
            error: error instanceof Error ? error.message : "No pudimos consultar los horarios ocupados.",
            cargando: false,
          });
        });
    }
    return () => { cancelled = true; };
  }, [effectiveAreaId, fechaReserva, claveConsulta]);

  useEffect(() => {
    const actualizar = () => setRevisionCalendario((value) => value + 1);
    window.addEventListener("focus", actualizar);
    return () => window.removeEventListener("focus", actualizar);
  }, []);

  async function handleCrearReserva(e: React.FormEvent) {
    e.preventDefault();
    setReservaError(null);
    setReservaSuccess(null);
    if (!departamentoId || !condominioId) {
      setReservaError("Selecciona una unidad autorizada y su condominio.");
      return;
    }

    if (estaEnMora) {
      setReservaError("No puedes reservar áreas comunes mientras mantengas cuotas vencidas.");
      return;
    }

    if (!effectiveAreaId) {
      setReservaError("Selecciona un espacio común.");
      return;
    }
    if (!fechaReserva || !inicioEnFuturo(fechaReserva, horaInicio)) {
      setReservaError("Elige una fecha y una hora de inicio futuras en hora de Lima.");
      return;
    }
    if (cargandoDisponibilidad || !consultaVigente || errorDisponibilidad) {
      setReservaError("Consulta los horarios de esta fecha antes de confirmar la reserva.");
      return;
    }
    if (horaInicio < apertura || horaFin > cierre || horaFin <= horaInicio || minutos(horaFin) - minutos(horaInicio) > duracionMaxima * 60) {
      setReservaError("Elige un turno dentro del horario y de la duración máxima del área.");
      return;
    }
    if (turnoOcupado) {
      setReservaError("El turno coincide con un horario ocupado. Elige otra franja.");
      return;
    }

    setIsSubmitting(true);
    const res = await crearReserva({
      condominio_id: condominioId,
      area_id: effectiveAreaId,
      departamento_id: departamentoId,
      fecha_reserva: fechaReserva,
      hora_inicio: horaInicio,
      hora_fin: horaFin,
    });

    setIsSubmitting(false);

    if (res.ok) {
      setRevisionCalendario((value) => value + 1);
      setReservaSuccess("Reserva confirmada. Puedes consultar su horario y tarifa en Mis reservas.");
      if (onSuccess) onSuccess();
    } else {
      setRevisionCalendario((value) => value + 1);
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
              onChange={(e) => {
                setSelectedAreaId(e.target.value);
                setRevisionCalendario((value) => value + 1);
              }}
              disabled={isSubmitting || areas.length === 0}
            >
              {areas.length === 0 ? (
                <option value="">No hay espacios disponibles</option>
              ) : (
                areas.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.nombre} ({formatMoney(a.costo_reserva, a.moneda)})
                  </option>
                ))
              )}
            </Select>
          </Field>

          {seleccionada && <div className="rounded-lg border border-line bg-canvas p-3 text-sm" aria-label="Condiciones del área seleccionada">
            <p>{seleccionada.descripcion}</p>
            <p>Horario diario: {apertura}–{cierre} · Hora de Lima</p>
            <p>Máximo {duracionMaxima} horas por reserva · Aforo {seleccionada.aforo_maximo} personas</p>
            <p>Tarifa por turno: {formatMoney(seleccionada.costo_reserva, seleccionada.moneda)}</p>
            {seleccionada.edificio_nombre && <p>Uso exclusivo: {seleccionada.edificio_nombre}</p>}
          </div>}

          <Field label="Fecha de Reserva" required>
            <Input
              type="date"
              min={getTodayLima()}
              required
              value={fechaReserva}
              onChange={(e) => {
                setFechaReserva(e.target.value);
                setRevisionCalendario((value) => value + 1);
              }}
              disabled={isSubmitting}
            />
          </Field>

          {effectiveAreaId && fechaReserva && (
            <div className="space-y-2 rounded-lg border border-line bg-canvas p-3 text-sm" aria-live="polite" aria-busy={cargandoDisponibilidad}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">Ocupación del área · Hora de Lima</p>
                <Button variant="ghost" size="sm" disabled={cargandoDisponibilidad || isSubmitting}
                  onClick={() => setRevisionCalendario((value) => value + 1)}>
                  {errorDisponibilidad ? "Reintentar" : "Actualizar"}
                </Button>
              </div>
              {cargandoDisponibilidad ? (
                <Spinner label="Consultando horarios…" />
              ) : errorDisponibilidad ? (
                <Alert tone="warning">{errorDisponibilidad}</Alert>
              ) : ocupados.length > 0 ? (
                <ul>{ocupados.map((h) => <li key={`${h.hora_inicio}-${h.hora_fin}`}>
                  {h.hora_inicio.slice(0, 5)} – {h.hora_fin.slice(0, 5)}
                </li>)}</ul>
              ) : (
                <p>No hay horarios ocupados dentro del horario de uso para esta fecha.</p>
              )}
              <p className="text-xs text-muted">El turno debe respetar la apertura, el cierre y la duración máxima. Para hoy, el inicio debe ser futuro. La disponibilidad se confirma al reservar.</p>
            </div>
          )}

          {turnoOcupado && <Alert tone="warning">El turno seleccionado coincide con un horario ocupado. Elige otra franja.</Alert>}

          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Hora Inicio" required>
              <Input
                type="time"
                required
                min={apertura}
                max={cierre}
                step={60}
                value={horaInicio}
                onChange={(e) => setHoraInicio(e.target.value)}
                disabled={estaEnMora}
              />
            </Field>

            <Field label="Hora Fin" required>
              <Input
                type="time"
                required
                min={apertura}
                max={cierre}
                step={60}
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
                disabled={areas.length === 0 || !fechaReserva || cargandoDisponibilidad || !consultaVigente || Boolean(errorDisponibilidad) || turnoOcupado}
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
