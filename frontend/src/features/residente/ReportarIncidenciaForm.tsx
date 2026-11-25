"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import { ApiError, registrarIncidencia, type RegistroIncidencia } from "@/lib/api";

const CAMPOS = {
  ubicacion: "Indica dónde ocurrió.",
  categoria: "Indica el tipo de desperfecto.",
  descripcion: "Describe qué ocurrió.",
  urgencia: "Selecciona un nivel de urgencia.",
};
const MAX_FOTO = 3 * 1024 * 1024;

type Campo = keyof typeof CAMPOS;

export function ReportarIncidenciaForm({ departamentoId }: { departamentoId: string }) {
  const clave = useRef<string>();
  const enCurso = useRef(false);
  const [errores, setErrores] = useState<Partial<Record<Campo, string>>>({});
  const [error, setError] = useState("");
  const [errorFoto, setErrorFoto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [resultado, setResultado] = useState<RegistroIncidencia>();

  async function enviar(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (enCurso.current) return;
    const form = event.currentTarget;
    const datos = new FormData(form);
    const pendientes: Partial<Record<Campo, string>> = {};
    for (const campo of Object.keys(CAMPOS) as Campo[]) {
      const valor = String(datos.get(campo) ?? "").trim();
      if (!valor) pendientes[campo] = CAMPOS[campo];
      datos.set(campo, valor);
    }
    setErrores(pendientes);
    setError("");
    const primerError = Object.keys(pendientes)[0];
    if (primerError) {
      const control = form.elements.namedItem(primerError);
      if (control instanceof HTMLElement) control.focus();
      return;
    }

    if (!(datos.get("evidencia") as File | null)?.name) datos.delete("evidencia");
    datos.set("departamento_id", departamentoId);
    enCurso.current = true;
    setEnviando(true);
    try {
      clave.current ??= crypto.randomUUID();
      setResultado(await registrarIncidencia(datos, clave.current));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No pudimos enviar el reporte. Inténtalo de nuevo.");
    } finally {
      enCurso.current = false;
      setEnviando(false);
    }
  }

  return (
    <Card className="max-w-3xl">
      <CardHeader
        title="Reportar una incidencia"
        description="Describe el desperfecto para que la administración pueda revisarlo."
      />
      <CardBody>
        {resultado ? (
          <div className="space-y-4">
            <Alert tone="success" title="Incidencia registrada">
              <span className="block break-all">Código {resultado.id}</span>
              <Link className="font-medium underline underline-offset-2" href={`/incidencias/${resultado.id}`}>
                Ver reporte
              </Link>
            </Alert>
            {resultado.advertencia_evidencia && (
              <Alert tone="warning" title="El reporte quedó guardado sin foto">
                {resultado.advertencia_evidencia}
              </Alert>
            )}
            <Button variant="secondary" onClick={() => {
              clave.current = undefined;
              setErrorFoto("");
              setResultado(undefined);
            }}>
              Reportar otra incidencia
            </Button>
          </div>
        ) : (
          <form
            noValidate
            onSubmit={enviar}
            onChange={() => { clave.current = undefined; }}
          >
            <fieldset disabled={enviando} className="grid gap-4 sm:grid-cols-2">
              <Field label="Ubicación" required error={errores.ubicacion}>
                <Input name="ubicacion" maxLength={160} placeholder="Torre B, pasillo del piso 4" />
              </Field>
              <Field label="Categoría" required error={errores.categoria}>
                <Input name="categoria" maxLength={80} placeholder="Iluminación, ascensores, limpieza…" />
              </Field>
              <Field label="Descripción" className="sm:col-span-2" required error={errores.descripcion}>
                <Textarea name="descripcion" maxLength={2000} placeholder="Cuéntanos qué pasó." />
              </Field>
              <Field label="Urgencia" required error={errores.urgencia}>
                <Select name="urgencia" defaultValue="">
                  <option value="" disabled>Selecciona una opción</option>
                  <option value="BAJA">Baja</option>
                  <option value="MEDIA">Media</option>
                  <option value="ALTA">Alta</option>
                  <option value="URGENTE">Urgente</option>
                </Select>
              </Field>
              <Field label="Foto opcional" hint="JPEG o PNG de hasta 3 MiB." error={errorFoto}>
                <Input
                  name="evidencia"
                  type="file"
                  accept="image/jpeg,image/png"
                  onChange={(event) => {
                    const foto = event.target.files?.[0];
                    setErrorFoto("");
                    if (!foto) return;
                    if ((foto.type && !["image/jpeg", "image/png"].includes(foto.type)) || foto.size > MAX_FOTO) {
                      event.target.value = "";
                      setErrorFoto("Usa un JPEG o PNG de hasta 3 MiB. Puedes enviar el reporte sin foto.");
                    }
                  }}
                />
              </Field>
              {error && <Alert tone="danger" className="sm:col-span-2">{error}</Alert>}
              <div className="sm:col-span-2 sm:text-right">
                <Button type="submit" loading={enviando} loadingText="Enviando…" className="w-full sm:w-auto">
                  Enviar reporte
                </Button>
              </div>
            </fieldset>
          </form>
        )}
      </CardBody>
    </Card>
  );
}
