"use client";

import { useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import {
  ApiError,
  NIVELES_INCIDENCIA,
  revisarIncidencia,
  type Incidencia,
  type RevisionIncidencia,
  type UrgenciaIncidencia,
} from "@/lib/api";

interface Props {
  incidencia: Incidencia;
  onActualizada: (incidencia: Incidencia) => void;
  onRecargar: () => void;
}

export function RevisionIncidenciaForm({ incidencia, onActualizada, onRecargar }: Props) {
  const [ocupada, setOcupada] = useState(false);
  const [rechazando, setRechazando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const [error, setError] = useState("");
  const [errorMotivo, setErrorMotivo] = useState("");
  const [conflicto, setConflicto] = useState(false);

  async function guardar(revision: RevisionIncidencia) {
    if (ocupada || conflicto) return;
    setOcupada(true);
    setError("");
    setErrorMotivo("");
    try {
      const detalle = await revisarIncidencia(incidencia.id, revision);
      setRechazando(false);
      onActualizada(detalle);
    } catch (causa) {
      if (causa instanceof ApiError && causa.status === 409) {
        setConflicto(true);
        setRechazando(false);
        setError(causa.message);
      } else {
        const mensaje = causa instanceof ApiError ? causa.message : "No pudimos guardar la revisión.";
        if (revision.accion === "RECHAZAR") setErrorMotivo(mensaje);
        else setError(mensaje);
      }
    } finally {
      setOcupada(false);
    }
  }

  function clasificar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const datos = new FormData(event.currentTarget);
    const categoria = String(datos.get("categoria") ?? "").trim();
    if (!categoria) {
      setError("Escribe la categoría de la incidencia.");
      return;
    }
    void guardar({
      accion: "CLASIFICAR",
      version: incidencia.version,
      categoria,
      prioridad: String(datos.get("prioridad")) as UrgenciaIncidencia,
    });
  }

  function rechazar() {
    const texto = motivo.trim();
    if (!texto) {
      setErrorMotivo("Escribe el motivo del rechazo.");
      return;
    }
    void guardar({ accion: "RECHAZAR", version: incidencia.version, motivo: texto });
  }

  return (
    <Card>
      <CardHeader title="Revisión de Junta" />
      <CardBody>
        <form onSubmit={clasificar} className="space-y-4">
          <fieldset disabled={ocupada || conflicto} className="grid gap-4 sm:grid-cols-2">
            <Field label="Categoría" required>
              <Input name="categoria" maxLength={80} defaultValue={incidencia.categoria_confirmada ?? incidencia.categoria} />
            </Field>
            <Field label="Prioridad" required>
              <Select name="prioridad" defaultValue={incidencia.prioridad ?? incidencia.urgencia}>
                {Object.entries(NIVELES_INCIDENCIA).map(([nivel, etiqueta]) => (
                  <option key={nivel} value={nivel}>{etiqueta}</option>
                ))}
              </Select>
            </Field>
          </fieldset>
          {error && (
            <Alert
              tone={conflicto ? "warning" : "danger"}
              action={conflicto && <Button variant="secondary" size="sm" onClick={onRecargar}>Cargar versión actual</Button>}
            >
              {error}
            </Alert>
          )}
          <div className="flex flex-wrap justify-between gap-3">
            <Button variant="secondary" onClick={() => {
              setMotivo("");
              setErrorMotivo("");
              setRechazando(true);
            }} disabled={ocupada || conflicto}>
              Rechazar incidencia
            </Button>
            <Button type="submit" loading={ocupada && !rechazando} disabled={conflicto}>
              Guardar clasificación
            </Button>
          </div>
        </form>
      </CardBody>
      <ConfirmDialog
        open={rechazando}
        title="Rechazar incidencia"
        tone="danger"
        confirmLabel="Confirmar rechazo"
        loading={ocupada}
        onCancel={() => { if (!ocupada) setRechazando(false); }}
        onConfirm={rechazar}
      >
        <Field label="Motivo del rechazo" hint="El residente podrá leer este motivo." error={errorMotivo} required>
          <Textarea value={motivo} onChange={(event) => setMotivo(event.target.value)} maxLength={1000} disabled={ocupada} />
        </Field>
      </ConfirmDialog>
    </Card>
  );
}
