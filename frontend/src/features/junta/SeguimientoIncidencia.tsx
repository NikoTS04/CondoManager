"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input, Textarea } from "@/components/ui/Field";
import { RepartoCosto } from "./RepartoCosto";
import { isPositiveMoney } from "@/lib/money";
import {
  ApiError,
  consultarHistorialIncidencia,
  descargarEvidenciaActualizacion,
  registrarSeguimientoIncidencia,
  resolverIncidencia,
  type ActualizacionIncidencia,
  type Incidencia,
} from "@/lib/api";

interface Props {
  incidencia: Incidencia;
  esJunta: boolean;
  onActualizada: (incidencia: Incidencia) => void;
}

export function SeguimientoIncidencia({ incidencia, esJunta, onActualizada }: Props) {
  const [historial, setHistorial] = useState<ActualizacionIncidencia[]>([]);
  const [error, setError] = useState("");
  const [ocupada, setOcupada] = useState(false);
  const [hayMas, setHayMas] = useState(false);
  const [cargandoMas, setCargandoMas] = useState(false);

  useEffect(() => {
    const control = new AbortController();
    consultarHistorialIncidencia(incidencia.id, control.signal)
      .then((lista) => {
        if (!control.signal.aborted) {
          setHistorial(lista.items);
          setHayMas(lista.hay_mas);
        }
      })
      .catch(() => undefined);
    return () => control.abort();
  }, [incidencia.id, incidencia.version]);

  async function cargarMas() {
    setCargandoMas(true);
    setError("");
    try {
      const lista = await consultarHistorialIncidencia(incidencia.id, undefined, historial.length);
      setHistorial((previo) => [...previo, ...lista.items]);
      setHayMas(lista.hay_mas);
    } catch {
      setError("No pudimos cargar los costos y avances anteriores.");
    } finally { setCargandoMas(false); }
  }

  async function guardar(evento: FormEvent<HTMLFormElement>, resolver: boolean) {
    evento.preventDefault();
    setError("");
    const datos = new FormData(evento.currentTarget);
    datos.set("version", String(incidencia.version));
    setOcupada(true);
    try {
      const actualizada = resolver
        ? await resolverIncidencia(incidencia.id, datos)
        : await registrarSeguimientoIncidencia(incidencia.id, datos);
      onActualizada(actualizada);
    } catch (causa) {
      setError(causa instanceof ApiError ? causa.message : "No pudimos guardar el avance.");
    } finally {
      setOcupada(false);
    }
  }

  const puedeAvanzar = esJunta && ["ASIGNADO", "EN_PROCESO"].includes(incidencia.estado);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader title="Historial de seguimiento" description="Fechas, actores y cambios de estado." />
        <CardBody>
          {historial.length === 0 ? (
            <p className="text-sm text-muted">Aún no hay actualizaciones registradas.</p>
          ) : (
            <ol className="space-y-3">
              {historial.map((item) => (
                <li key={item.id} className="rounded-lg border border-line p-3 text-sm">
                  <div className="flex flex-wrap justify-between gap-2">
                    <span className="font-semibold">
                      {item.tipo === "COSTO" ? "Costo registrado" : "Actualización"}
                      {item.estado_nuevo && ` · ${item.estado_nuevo.toLowerCase().replace("_", " ")}`}
                    </span>
                    <time className="text-muted" dateTime={item.creado_en}>
                      {new Date(item.creado_en).toLocaleString("es-PE")}
                    </time>
                  </div>
                  <p className="mt-1 whitespace-pre-wrap break-words">{item.descripcion}</p>
                  {item.repuesto && <p className="mt-1 text-muted">Repuesto: {item.repuesto}</p>}
                  {item.monto && <p className="mt-1 text-muted">Monto: S/ {item.monto}</p>}
                  {esJunta && item.monto && isPositiveMoney(item.monto) &&
                    <RepartoCosto incidenciaId={incidencia.id} costoId={item.id} />}
                  {item.tiene_evidencia && (
                    <button
                      type="button"
                      className="mt-2 text-sm font-medium text-brand-700 underline"
                      onClick={() => {
                        void descargarEvidenciaActualizacion(incidencia.id, item.id).catch(() =>
                          setError("No pudimos descargar la evidencia."),
                        );
                      }}
                    >
                      Descargar evidencia
                    </button>
                  )}
                </li>
              ))}
            </ol>
          )}
          {error && <Alert tone="danger">{error}</Alert>}
          {hayMas && <Button type="button" variant="secondary" loading={cargandoMas}
            onClick={() => void cargarMas()}>Cargar avances y costos anteriores</Button>}
        </CardBody>
      </Card>

      {puedeAvanzar && (
        <Card>
          <CardHeader
            title="Registrar avance"
            description="Los costos y sustentos internos no se muestran al residente si se marcan como privados."
          />
          <CardBody>
            <form className="space-y-4" onSubmit={(evento) => void guardar(evento, false)}>
              <Field label="Comentario o diagnóstico" required>
                <Textarea name="comentario" maxLength={2000} rows={3} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Repuesto">
                  <Input name="repuesto" maxLength={120} />
                </Field>
                <Field label="Monto (S/)">
                  <Input name="monto" inputMode="decimal" placeholder="0.00" />
                </Field>
              </div>
              <Field label="Evidencia (JPEG o PNG, hasta 3 MiB)">
                <Input name="evidencia" type="file" accept="image/jpeg,image/png" />
              </Field>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" name="publico" value="true" defaultChecked />
                Visible para el residente
              </label>
              <Button type="submit" loading={ocupada} loadingText="Guardando…">
                Guardar avance
              </Button>
            </form>
            {incidencia.estado === "EN_PROCESO" && (
              <form className="mt-6 space-y-4 border-t border-line pt-4" onSubmit={(evento) => void guardar(evento, true)}>
                <Field label="Descripción de la resolución" required>
                  <Textarea name="descripcion" maxLength={2000} rows={3} />
                </Field>
                <div className="grid gap-4 sm:grid-cols-2">
                  <Field label="Repuesto final">
                    <Input name="repuesto" maxLength={120} />
                  </Field>
                  <Field label="Monto final (S/)">
                    <Input name="monto" inputMode="decimal" placeholder="0.00" />
                  </Field>
                </div>
                <Field label="Evidencia de la resolución">
                  <Input name="evidencia" type="file" accept="image/jpeg,image/png" />
                </Field>
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" name="publico" value="true" defaultChecked />
                  Visible para el residente
                </label>
                <Button type="submit" variant="secondary" loading={ocupada} loadingText="Guardando…">
                  Marcar como resuelta
                </Button>
              </form>
            )}
          </CardBody>
        </Card>
      )}
    </div>
  );
}
