"use client";

import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Select, Textarea } from "@/components/ui/Field";
import {
  ApiError,
  cerrarAdministrativamenteIncidencia,
  confirmarIncidencia,
  reabrirIncidencia,
  type Incidencia,
} from "@/lib/api";

interface Props {
  incidencia: Incidencia;
  esJunta: boolean;
  onActualizada: (incidencia: Incidencia) => void;
}

export function CierreIncidencia({ incidencia, esJunta, onActualizada }: Props) {
  const [error, setError] = useState("");
  const [ocupada, setOcupada] = useState(false);

  async function ejecutar(
    accion: "confirmar" | "reabrir" | "cerrar",
    evento: FormEvent<HTMLFormElement>,
  ) {
    evento.preventDefault();
    setError("");
    const datos = new FormData(evento.currentTarget);
    const motivo = String(datos.get("motivo") ?? "").trim();
    if (accion !== "confirmar" && !motivo) {
      setError("Escribe el motivo antes de continuar.");
      return;
    }
    setOcupada(true);
    try {
      const actualizada =
        accion === "confirmar"
          ? await confirmarIncidencia(
              incidencia.id,
              incidencia.version,
              Number(datos.get("calificacion")),
              String(datos.get("comentario") ?? "").trim(),
            )
          : accion === "reabrir"
            ? await reabrirIncidencia(incidencia.id, incidencia.version, motivo)
            : await cerrarAdministrativamenteIncidencia(incidencia.id, incidencia.version, motivo);
      onActualizada(actualizada);
    } catch (causa) {
      setError(causa instanceof ApiError ? causa.message : "No pudimos guardar la decisión.");
    } finally {
      setOcupada(false);
    }
  }

  if (incidencia.estado !== "RESUELTO") return null;

  return (
    <Card>
      <CardHeader
        title={esJunta ? "Cierre administrativo" : "Confirma la solución"}
        description={
          esJunta
            ? "Puedes cerrar el ticket con una decisión autorizada y motivo."
            : "Califica la atención o reabre el caso si no estás conforme."
        }
      />
      <CardBody className="space-y-4">
        {error && <Alert tone="danger">{error}</Alert>}
        {esJunta ? (
          <form onSubmit={(evento) => void ejecutar("cerrar", evento)} className="space-y-3">
            <Field label="Motivo de la decisión" required>
              <Textarea name="motivo" maxLength={1000} rows={3} />
            </Field>
            <Button type="submit" loading={ocupada} loadingText="Guardando…">
              Cerrar ticket
            </Button>
          </form>
        ) : (
          <div className="space-y-5">
            <form onSubmit={(evento) => void ejecutar("confirmar", evento)} className="space-y-3">
              <Field label="Calificación de la atención" required>
                <Select name="calificacion" defaultValue="5">
                  {[1, 2, 3, 4, 5].map((nota) => (
                    <option key={nota} value={nota}>
                      {nota} de 5
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="Comentario opcional">
                <Textarea name="comentario" maxLength={1000} rows={2} />
              </Field>
              <Button type="submit" loading={ocupada} loadingText="Guardando…">
                Confirmar y cerrar
              </Button>
            </form>
            <form
              onSubmit={(evento) => void ejecutar("reabrir", evento)}
              className="space-y-3 border-t border-line pt-4"
            >
              <Field label="Motivo de la reapertura" required>
                <Textarea name="motivo" maxLength={1000} rows={3} />
              </Field>
              <Button type="submit" variant="secondary" loading={ocupada} loadingText="Guardando…">
                No estoy conforme, reabrir
              </Button>
            </form>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
