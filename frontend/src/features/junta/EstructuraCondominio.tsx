"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  Building2,
  Download,
  FileSpreadsheet,
  Plus,
  Upload,
} from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import { Field, Input } from "@/components/ui/Field";
import { cn } from "@/lib/cn";
import {
  cambiarEstadoDepartamento,
  importarEstructura,
  listarEdificios,
  registrarDepartamento,
  registrarEdificio,
  type DepartamentoRegistrado,
  type Edificio,
  type ResultadoImportacion,
} from "@/lib/api";
import { formatPercent } from "@/lib/money";

interface Props {
  condominioId: string | null;
  departamentos: DepartamentoRegistrado[];
  soloLectura?: boolean;
  cargando?: boolean;
  onActualizar: () => Promise<void>;
}

function descargarCsv(nombre: string, filas: (string | number)[][]) {
  const contenido = filas
    .map((fila) =>
      fila
        .map((valor) => {
          const texto = String(valor);
          return /[",;\r\n]/.test(texto)
            ? `"${texto.replace(/"/g, '""')}"`
            : texto;
        })
        .join(","),
    )
    .join("\r\n");
  const url = URL.createObjectURL(
    new Blob(["\uFEFF", contenido], { type: "text/csv;charset=utf-8" }),
  );
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(url);
}

function sumarCoeficientes(unidades: DepartamentoRegistrado[]): string {
  const suma = unidades
    .filter((d) => d.activo)
    .reduce((total, d) => {
      const [entero, decimales = ""] = d.coeficiente_participacion.split(".");
      return (
        total +
        BigInt(entero) * BigInt(10000) +
        BigInt(decimales.padEnd(4, "0"))
      );
    }, BigInt(0));
  return `${suma / BigInt(10000)}.${(suma % BigInt(10000)).toString().padStart(4, "0")}`;
}

export function EstructuraCondominio({
  condominioId,
  departamentos,
  soloLectura = false,
  cargando = false,
  onActualizar,
}: Props) {
  const [edificios, setEdificios] = useState<Edificio[]>([]);
  const [edificioActivo, setEdificioActivo] = useState("");
  const [nombre, setNombre] = useState("");
  const [totalPisos, setTotalPisos] = useState("");
  const [numero, setNumero] = useState("");
  const [piso, setPiso] = useState("");
  const [coeficiente, setCoeficiente] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [busy, setBusy] = useState(false);
  const [cargandoEdificios, setCargandoEdificios] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [archivo, setArchivo] = useState<File | null>(null);
  const [resultado, setResultado] = useState<ResultadoImportacion | null>(null);

  useEffect(() => {
    if (!condominioId) {
      setCargandoEdificios(false);
      return;
    }
    let cancelado = false;
    setCargandoEdificios(true);
    void listarEdificios(condominioId)
      .then((datos) => {
        if (cancelado) return;
        setEdificios(datos);
        setEdificioActivo((actual) =>
          datos.some((e) => e.id === actual) ? actual : (datos[0]?.id ?? ""),
        );
      })
      .catch((causa: unknown) => {
        if (!cancelado)
          setError(
            causa instanceof Error
              ? causa.message
              : "No se pudieron cargar los edificios.",
          );
      })
      .finally(() => {
        if (!cancelado) setCargandoEdificios(false);
      });
    return () => {
      cancelado = true;
    };
  }, [condominioId, departamentos]);

  const seleccionado = edificios.find((e) => e.id === edificioActivo);
  const visibles = useMemo(
    () =>
      departamentos.filter(
        (d) =>
          d.edificio_id === edificioActivo &&
          d.numero.toLowerCase().includes(busqueda.trim().toLowerCase()),
      ),
    [departamentos, edificioActivo, busqueda],
  );

  if (!condominioId)
    return (
      <EmptyState
        title="Selecciona un condominio"
        description="Crea o selecciona un condominio en Configuración para registrar su estructura."
      />
    );

  async function ejecutar(accion: () => Promise<string>) {
    setBusy(true);
    setError(null);
    setMensaje(null);
    try {
      setMensaje(await accion());
    } catch (causa) {
      setError(
        causa instanceof Error
          ? causa.message
          : "No se pudo completar la operación.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function crearEdificio(event: FormEvent) {
    event.preventDefault();
    if (!condominioId || soloLectura) return;
    await ejecutar(async () => {
      const creado = await registrarEdificio(
        condominioId,
        nombre.trim(),
        Number(totalPisos),
      );
      setEdificios(await listarEdificios(condominioId));
      setEdificioActivo(creado.id);
      setNombre("");
      setTotalPisos("");
      await onActualizar();
      return "Edificio guardado en la base de datos.";
    });
  }

  async function crearDepartamento(event: FormEvent) {
    event.preventDefault();
    if (!condominioId || !edificioActivo || soloLectura) return;
    await ejecutar(async () => {
      await registrarDepartamento(condominioId, edificioActivo, {
        numero: numero.trim(),
        piso: Number(piso),
        coeficiente_participacion: coeficiente.trim().replace(",", "."),
      });
      setNumero("");
      setPiso("");
      setCoeficiente("");
      await onActualizar();
      return "Departamento guardado en la base de datos.";
    });
  }

  async function procesarArchivo(
    confirmar: boolean,
    seleccionado: File | null = archivo,
  ) {
    if (!condominioId || !seleccionado || soloLectura) return;
    await ejecutar(async () => {
      const respuesta = await importarEstructura(
        condominioId,
        seleccionado,
        confirmar,
      );
      setResultado(respuesta);
      if (confirmar) {
        const datos = await listarEdificios(condominioId);
        setEdificios(datos);
        setEdificioActivo((actual) =>
          datos.some((e) => e.id === actual) ? actual : (datos[0]?.id ?? ""),
        );
        await onActualizar();
      }
      return confirmar
        ? `${respuesta.creadas} creadas · ${respuesta.ya_existentes} ya existentes · ${respuesta.rechazadas} con error.`
        : "Vista previa validada. Revisa el resultado antes de importar.";
    });
  }

  const cabecera = ["numero", "piso", "edificio", "coeficiente", "total_pisos"];
  const loading = cargando || cargandoEdificios;

  return (
    <div className="space-y-6">
      {soloLectura && (
        <Alert tone="info">Consulta de estructura en modo solo lectura.</Alert>
      )}
      {error && (
        <Alert tone="danger" title="No se pudo completar la operación">
          {error}
        </Alert>
      )}
      {mensaje && <Alert tone="success">{mensaje}</Alert>}
      <section
        aria-label="Indicadores de estructura"
        className="grid gap-4 md:grid-cols-3"
      >
        <Indicador titulo="Edificios" valor={String(edificios.length)} />
        <Indicador
          titulo="Departamentos activos"
          valor={String(departamentos.filter((d) => d.activo).length)}
        />
        <Indicador
          titulo="Alícuotas activas del condominio"
          valor={formatPercent(sumarCoeficientes(departamentos))}
        />
      </section>
      <div className="grid gap-6 xl:grid-cols-[minmax(16rem,280px)_minmax(0,1fr)]">
        <Card>
          <CardHeader
            title="Edificios"
            icon={<Building2 className="h-5 w-5" aria-hidden="true" />}
          />
          <CardBody className="space-y-4">
            {loading ? (
              <SkeletonList rows={3} label="Cargando edificios" />
            ) : edificios.length === 0 ? (
              <EmptyState
                title="Sin edificios"
                description="Agrega un edificio para empezar."
              />
            ) : (
              <ul className="space-y-2">
                {edificios.map((e) => (
                  <li key={e.id}>
                    <button
                      type="button"
                      aria-current={
                        e.id === edificioActivo ? "true" : undefined
                      }
                      onClick={() => setEdificioActivo(e.id)}
                      className={cn(
                        "min-h-11 w-full rounded-lg border px-3 py-2 text-left text-sm",
                        e.id === edificioActivo
                          ? "border-info-200 bg-info-50 text-info-800"
                          : "border-line hover:bg-canvas",
                      )}
                    >
                      {e.nombre_bloque} · {e.total_pisos} pisos
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {!soloLectura && (
              <form
                onSubmit={crearEdificio}
                className="space-y-3 border-t border-line pt-4"
              >
                <Field label="Nuevo edificio" required>
                  <Input
                    required
                    maxLength={100}
                    value={nombre}
                    onChange={(e) => setNombre(e.target.value)}
                    placeholder="Torre A"
                  />
                </Field>
                <Field label="Total de pisos" required>
                  <Input
                    required
                    type="number"
                    min={1}
                    max={32767}
                    step={1}
                    value={totalPisos}
                    onChange={(e) => setTotalPisos(e.target.value)}
                  />
                </Field>
                <Button
                  type="submit"
                  disabled={busy}
                  icon={<Plus className="h-4 w-4" aria-hidden="true" />}
                >
                  Agregar edificio
                </Button>
              </form>
            )}
          </CardBody>
        </Card>
        <div className="space-y-6">
          <Card>
            <CardHeader
              title={seleccionado?.nombre_bloque ?? "Departamentos"}
              description="El número es único dentro del edificio. Los cambios se guardan en la base de datos."
              actions={
                <Button
                  variant="secondary"
                  disabled={loading || departamentos.length === 0}
                  icon={<Download className="h-4 w-4" aria-hidden="true" />}
                  onClick={() =>
                    descargarCsv("estructura-condominio.csv", [
                      cabecera,
                      ...departamentos.map((d) => {
                        const e = edificios.find((e) => e.id === d.edificio_id);
                        return [
                          d.numero,
                          d.piso,
                          e?.nombre_bloque ?? "",
                          d.coeficiente_participacion,
                          e?.total_pisos ?? "",
                        ];
                      }),
                    ])
                  }
                >
                  Exportar CSV
                </Button>
              }
            />
            <CardBody className="space-y-6">
              {!soloLectura && (
                <form
                  onSubmit={crearDepartamento}
                  className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"
                >
                  <Field label="Número" required>
                    <Input
                      required
                      maxLength={20}
                      value={numero}
                      onChange={(e) => setNumero(e.target.value)}
                    />
                  </Field>
                  <Field label="Piso" required>
                    <Input
                      required
                      type="number"
                      min={1}
                      max={seleccionado?.total_pisos ?? 32767}
                      step={1}
                      value={piso}
                      onChange={(e) => setPiso(e.target.value)}
                    />
                  </Field>
                  <Field label="Coeficiente (%)" required>
                    <Input
                      required
                      inputMode="decimal"
                      placeholder="0.7200"
                      value={coeficiente}
                      onChange={(e) => setCoeficiente(e.target.value)}
                    />
                  </Field>
                  <Button
                    type="submit"
                    className="self-end"
                    disabled={busy || loading || !seleccionado}
                  >
                    Registrar
                  </Button>
                </form>
              )}
              <Field label="Buscar departamento">
                <Input
                  value={busqueda}
                  onChange={(e) => setBusqueda(e.target.value)}
                  placeholder="Número"
                />
              </Field>
              {loading ? (
                <SkeletonList rows={5} label="Cargando departamentos" />
              ) : visibles.length === 0 ? (
                <EmptyState
                  title="Sin departamentos"
                  description="Registra o importa unidades para este edificio."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[550px] text-sm">
                    <caption className="sr-only">
                      Departamentos del edificio seleccionado
                    </caption>
                    <thead>
                      <tr className="border-b border-line text-left">
                        <th className="p-3" scope="col">
                          Número
                        </th>
                        <th className="p-3" scope="col">
                          Piso
                        </th>
                        <th className="p-3" scope="col">
                          Coeficiente
                        </th>
                        <th className="p-3" scope="col">
                          Estado
                        </th>
                        {!soloLectura && (
                          <th className="p-3" scope="col">
                            Acción
                          </th>
                        )}
                      </tr>
                    </thead>
                    <tbody>
                      {visibles.map((d) => (
                        <tr key={d.id} className="border-b border-line">
                          <th scope="row" className="p-3 text-left">
                            {d.numero}
                          </th>
                          <td className="p-3">{d.piso}</td>
                          <td className="p-3 tabular-nums">
                            {formatPercent(d.coeficiente_participacion)}
                          </td>
                          <td className="p-3">
                            <Badge tone={d.activo ? "success" : "neutral"}>
                              {d.activo ? "Activo" : "Inactivo"}
                            </Badge>
                          </td>
                          {!soloLectura && (
                            <td className="p-3">
                              <Button
                                variant="secondary"
                                disabled={busy}
                                onClick={() =>
                                  void ejecutar(async () => {
                                    await cambiarEstadoDepartamento(
                                      condominioId,
                                      d.id,
                                      !d.activo,
                                    );
                                    await onActualizar();
                                    return `Departamento ${d.numero} ${d.activo ? "desactivado" : "activado"}.`;
                                  })
                                }
                              >
                                {d.activo ? "Desactivar" : "Activar"}
                              </Button>
                            </td>
                          )}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardBody>
          </Card>
          {!soloLectura && (
            <Card>
              <CardHeader
                title="Importación CSV"
                description="Vista previa validada por la API. Los reintentos omiten unidades idénticas."
                icon={
                  <FileSpreadsheet className="h-5 w-5" aria-hidden="true" />
                }
                actions={
                  <Button
                    variant="secondary"
                    onClick={() =>
                      descargarCsv("plantilla-departamentos.csv", [
                        cabecera,
                        ["101", 1, "Torre Norte", "0.7200", 14],
                        ["102", 1, "Torre Norte", "0.6800", 14],
                      ])
                    }
                  >
                    Descargar plantilla
                  </Button>
                }
              />
              <CardBody className="space-y-4">
                <Field
                  label="Archivo CSV"
                  hint="UTF-8 · máximo 2 MiB y 5000 filas · total_pisos obligatorio para edificios nuevos"
                >
                  <Input
                    type="file"
                    accept=".csv,text/csv"
                    disabled={busy}
                    onChange={(e) => {
                      const elegido = e.target.files?.[0] ?? null;
                      setArchivo(elegido);
                      setResultado(null);
                      if (elegido) void procesarArchivo(false, elegido);
                    }}
                  />
                </Field>
                {resultado && (
                  <>
                    <p className="text-sm">
                      {resultado.nuevas} nuevas · {resultado.creadas} creadas ·{" "}
                      {resultado.ya_existentes} existentes ·{" "}
                      {resultado.rechazadas} con error
                    </p>
                    <div className="max-h-96 overflow-auto">
                      <table className="w-full min-w-[650px] text-sm">
                        <caption className="sr-only">
                          Resultado de validación del CSV
                        </caption>
                        <thead>
                          <tr className="border-b border-line text-left">
                            {[
                              "Fila",
                              "Edificio",
                              "Número",
                              "Piso",
                              "Coeficiente",
                              "Resultado",
                            ].map((t) => (
                              <th key={t} scope="col" className="p-3">
                                {t}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {resultado.filas.map((f) => (
                            <tr key={f.fila} className="border-b border-line">
                              <th scope="row" className="p-3 text-left">
                                {f.fila}
                              </th>
                              <td className="p-3">{f.edificio}</td>
                              <td className="p-3">{f.numero}</td>
                              <td className="p-3">{f.piso ?? "—"}</td>
                              <td className="p-3">{f.coeficiente}</td>
                              <td className="p-3">
                                {f.errores.length
                                  ? f.errores.join(" · ")
                                  : f.estado.replaceAll("_", " ")}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <Button
                      disabled={busy || resultado.nuevas === 0}
                      onClick={() => void procesarArchivo(true)}
                      icon={<Upload className="h-4 w-4" aria-hidden="true" />}
                    >
                      Importar filas válidas
                    </Button>
                  </>
                )}
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function Indicador({ titulo, valor }: { titulo: string; valor: string }) {
  return (
    <Card>
      <CardBody>
        <p className="text-sm text-muted">{titulo}</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums">{valor}</p>
      </CardBody>
    </Card>
  );
}

export default EstructuraCondominio;
