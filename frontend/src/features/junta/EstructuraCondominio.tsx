"use client";

import {
  useEffect,
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import { Building2, Download, FileSpreadsheet, Plus, Search, Upload } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import { Field, Input } from "@/components/ui/Field";
import { cn } from "@/lib/cn";
import type { Departamento } from "@/lib/api";
import { formatPercent } from "@/lib/money";

interface Edificio {
  id: string;
  nombre: string;
}

interface DepartamentoEstructura extends Departamento {
  id: string;
  edificioId: string;
}

interface FilaImportacion {
  numero: string;
  piso: number;
  edificio: string;
  coeficiente: string;
  errores: string[];
}

interface EstructuraCondominioProps {
  departamentosIniciales: Departamento[];
  soloLectura?: boolean;
  cargando?: boolean;
}

const EDIFICIO_INICIAL: Edificio = { id: "edificio-3", nombre: "Edificio 3" };
const COEFICIENTE_MAXIMO = BigInt(1000000);

function leerCoeficiente(valor: string): bigint | null {
  const coincidencia = /^(\d+)(?:[.,](\d{1,4}))?$/.exec(valor.trim());
  if (!coincidencia) return null;
  const entero = coincidencia[1];
  const decimales = (coincidencia[2] ?? "").padEnd(4, "0");
  return BigInt(entero) * BigInt(10000) + BigInt(decimales || "0");
}

function normalizarCoeficiente(valor: string): string | null {
  const ticks = leerCoeficiente(valor);
  if (ticks === null || ticks <= BigInt(0) || ticks > COEFICIENTE_MAXIMO) return null;
  const entero = ticks / BigInt(10000);
  const decimales = (ticks % BigInt(10000)).toString().padStart(4, "0");
  return `${entero.toString()}.${decimales}`;
}

function sumarCoeficientes(coeficientes: string[]): string {
  const suma = coeficientes.reduce((total, coeficiente) => {
    const ticks = /^\d+\.\d{4}$/.test(coeficiente) ? leerCoeficiente(coeficiente) : null;
    return total + (ticks ?? BigInt(0));
  }, BigInt(0));
  const entero = suma / BigInt(10000);
  const decimales = (suma % BigInt(10000)).toString().padStart(4, "0");
  return `${entero.toString()}.${decimales}`;
}

function escaparCsv(valor: string | number): string {
  const texto = String(valor);
  return texto.includes(",") ? `"${texto.replace(/"/g, '""')}"` : texto;
}

function descargarCsv(nombre: string, contenido: string) {
  const url = URL.createObjectURL(new Blob([contenido], { type: "text/csv;charset=utf-8" }));
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = nombre;
  enlace.click();
  URL.revokeObjectURL(url);
}

export function EstructuraCondominio({
  departamentosIniciales,
  soloLectura = false,
  cargando = false,
}: EstructuraCondominioProps) {
  const [edificios, setEdificios] = useState<Edificio[]>([EDIFICIO_INICIAL]);
  const [departamentos, setDepartamentos] = useState<DepartamentoEstructura[]>([]);
  const [edificioActivo, setEdificioActivo] = useState(EDIFICIO_INICIAL.id);
  const [nuevoEdificio, setNuevoEdificio] = useState("");
  const [numero, setNumero] = useState("");
  const [piso, setPiso] = useState("");
  const [coeficiente, setCoeficiente] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [filasImportacion, setFilasImportacion] = useState<FilaImportacion[]>([]);
  const [nombreArchivo, setNombreArchivo] = useState("");
  const inputArchivoRef = useRef<HTMLInputElement>(null);
  const inicializados = useRef(false);

  useEffect(() => {
    if (inicializados.current || departamentosIniciales.length === 0) return;
    setDepartamentos(departamentosIniciales.map((departamento, indice) => ({
      ...departamento,
      id: `departamento-${indice + 1}`,
      edificioId: EDIFICIO_INICIAL.id,
    })));
    inicializados.current = true;
  }, [departamentosIniciales]);

  const edificioSeleccionado = edificios.find((edificio) => edificio.id === edificioActivo);
  const departamentosDelEdificio = useMemo(
    () => departamentos.filter((departamento) => (
      departamento.edificioId === edificioActivo &&
      departamento.numero.toLowerCase().includes(busqueda.trim().toLowerCase())
    )),
    [busqueda, departamentos, edificioActivo],
  );
  const coeficientesEdificio = departamentos
    .filter((departamento) => departamento.edificioId === edificioActivo)
    .map((departamento) => departamento.coeficiente);
  const sumaCoeficiente = sumarCoeficientes(coeficientesEdificio);

  function crearEdificio(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMensaje(null);
    if (soloLectura) return;
    const nombreLimpio = nuevoEdificio.trim();
    if (!nombreLimpio) return;
    if (edificios.some((edificio) => edificio.nombre.toLowerCase() === nombreLimpio.toLowerCase())) {
      setError("Ya existe un edificio con ese nombre.");
      return;
    }

    const edificio = { id: `edificio-${Date.now()}`, nombre: nombreLimpio };
    setEdificios((actuales) => [...actuales, edificio]);
    setEdificioActivo(edificio.id);
    setNuevoEdificio("");
    setMensaje(`${nombreLimpio} fue registrado correctamente.`);
  }

  function crearDepartamento(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMensaje(null);
    if (soloLectura) return;

    const numeroLimpio = numero.trim();
    if (!numeroLimpio || !/^\d+$/.test(piso)) {
      setError("Ingresa un número de departamento y un piso entero válido.");
      return;
    }
    const pisoValido = Number.parseInt(piso, 10);
    if (pisoValido < 1) {
      setError("El piso debe ser un entero mayor que cero.");
      return;
    }
    const coeficienteNormalizado = normalizarCoeficiente(coeficiente);
    if (!coeficienteNormalizado) {
      setError("El coeficiente debe ser mayor que 0 y menor o igual que 100.");
      return;
    }
    if (departamentos.some((departamento) => (
      departamento.edificioId === edificioActivo &&
      departamento.numero.toLowerCase() === numeroLimpio.toLowerCase()
    ))) {
      setError(`El departamento ${numeroLimpio} ya existe en ${edificioSeleccionado?.nombre}.`);
      return;
    }

    setDepartamentos((actuales) => [...actuales, {
      id: `departamento-${Date.now()}`,
      edificioId: edificioActivo,
      numero: numeroLimpio,
      piso: pisoValido,
      coeficiente: coeficienteNormalizado,
      saldo_a_favor: "0.00",
      estado_financiero: "AL_DIA",
      deuda_vencida: "0.00",
    }]);
    setNumero("");
    setPiso("");
    setCoeficiente("");
    setMensaje(`Departamento ${numeroLimpio} registrado correctamente.`);
  }

  function validarFila(columnas: string[], numeroFila: number): FilaImportacion {
    const [numeroCsv = "", pisoCsv = "", edificioCsv = "", coeficienteCsv = ""] =
      columnas.map((value) => value.trim());
    const errores: string[] = [];
    const pisoValido = /^\d+$/.test(pisoCsv) ? Number.parseInt(pisoCsv, 10) : null;
    const coeficienteNormalizado = normalizarCoeficiente(coeficienteCsv);

    if (!numeroCsv) errores.push(`Fila ${numeroFila}: falta el número`);
    if (pisoValido === null || pisoValido < 1) errores.push(`Fila ${numeroFila}: piso inválido`);
    if (!edificioCsv) errores.push(`Fila ${numeroFila}: falta el edificio`);
    if (!coeficienteNormalizado) errores.push(`Fila ${numeroFila}: coeficiente inválido`);

    const edificioExistente = edificios.find((edificio) => (
      edificio.nombre.toLowerCase() === edificioCsv.toLowerCase()
    ));
    if (edificioExistente && departamentos.some((departamento) => (
      departamento.edificioId === edificioExistente.id &&
      departamento.numero.toLowerCase() === numeroCsv.toLowerCase()
    ))) {
      errores.push(`Fila ${numeroFila}: departamento duplicado`);
    }

    return {
      numero: numeroCsv,
      piso: pisoValido ?? 0,
      edificio: edificioCsv,
      coeficiente: coeficienteNormalizado ?? coeficienteCsv,
      errores,
    };
  }

  async function seleccionarArchivo(event: ChangeEvent<HTMLInputElement>) {
    if (soloLectura) return;
    const archivo = event.target.files?.[0];
    if (!archivo) return;
    setNombreArchivo(archivo.name);
    setError(null);
    setMensaje(null);

    const lineas = (await archivo.text()).split(/\r?\n/).map((linea) => linea.trim()).filter(Boolean);
    const tieneCabecera = lineas[0]?.toLowerCase().includes("numero") ?? false;
    const datos = tieneCabecera ? lineas.slice(1) : lineas;
    const filas = datos.map((linea, indice) => {
      const separador = linea.includes(";") ? ";" : ",";
      return validarFila(linea.split(separador), indice + (tieneCabecera ? 2 : 1));
    });

    const vistas = new Set<string>();
    filas.forEach((fila) => {
      const clave = `${fila.edificio.toLowerCase()}::${fila.numero.toLowerCase()}`;
      if (vistas.has(clave)) fila.errores.push("Duplicado dentro del archivo");
      vistas.add(clave);
    });
    setFilasImportacion(filas);
  }

  function confirmarImportacion() {
    if (soloLectura) return;
    const validas = filasImportacion.filter((fila) => fila.errores.length === 0);
    const invalidas = filasImportacion.filter((fila) => fila.errores.length > 0);
    if (validas.length === 0) return;

    const nuevosEdificios = [...edificios];
    const nuevosDepartamentos = validas.map((fila, indice) => {
      let edificio = nuevosEdificios.find((actual) => (
        actual.nombre.toLowerCase() === fila.edificio.toLowerCase()
      ));
      if (!edificio) {
        edificio = { id: `edificio-importado-${Date.now()}-${indice}`, nombre: fila.edificio };
        nuevosEdificios.push(edificio);
      }
      return {
        id: `departamento-importado-${Date.now()}-${indice}`,
        edificioId: edificio.id,
        numero: fila.numero,
        piso: fila.piso,
        coeficiente: fila.coeficiente,
        saldo_a_favor: "0.00",
        estado_financiero: "AL_DIA" as const,
        deuda_vencida: "0.00",
      };
    });

    setEdificios(nuevosEdificios);
    setDepartamentos((actuales) => [...actuales, ...nuevosDepartamentos]);
    setFilasImportacion(invalidas);
    if (invalidas.length === 0) {
      setNombreArchivo("");
      if (inputArchivoRef.current) inputArchivoRef.current.value = "";
    }
    setMensaje(invalidas.length
      ? `${nuevosDepartamentos.length} unidades importadas; ${invalidas.length} filas requieren corrección.`
      : `${nuevosDepartamentos.length} unidades importadas correctamente.`);
  }

  function descargarPlantilla() {
    descargarCsv(
      "plantilla-departamentos.csv",
      ["numero,piso,edificio,coeficiente", "101,1,Torre Norte,0.7200", "102,1,Torre Norte,0.6800"].join("\n"),
    );
  }

  function exportarDepartamentos() {
    const lineas = departamentos.map((departamento) => [
      departamento.numero,
      departamento.piso.toString(),
      edificios.find((edificio) => edificio.id === departamento.edificioId)?.nombre ?? "",
      departamento.coeficiente,
    ]);
    const contenido = [
      "numero,piso,edificio,coeficiente",
      ...lineas.map((linea) => linea.map(escaparCsv).join(",")),
    ].join("\n");
    descargarCsv("estructura-condominio.csv", contenido);
  }

  const filasValidas = filasImportacion.filter((fila) => fila.errores.length === 0).length;
  const filasInvalidas = filasImportacion.length - filasValidas;

  return (
    <div className="space-y-6">
      {soloLectura && (
        <div className="rounded-lg border border-audit-200 bg-audit-50 p-4">
          <Badge tone="audit">Solo lectura</Badge>
          <p className="mt-2 text-sm text-audit-800">
            Puedes consultar y exportar la estructura; no están disponibles las acciones de escritura.
          </p>
        </div>
      )}
      {error && <Alert tone="danger" title="No se pudo actualizar la estructura">{error}</Alert>}
      {mensaje && <Alert tone="success" title="Estructura actualizada">{mensaje}</Alert>}

      <section aria-label="Indicadores de estructura" className="grid gap-4 md:grid-cols-3">
        <Indicador title="Edificios" valor={edificios.length.toString()} detalle="Estructuras registradas" />
        <Indicador
          title="Departamentos"
          valor={departamentos.length.toString()}
          detalle="Unidades inmobiliarias"
        />
        <Indicador
          title="Alícuotas del edificio"
          valor={formatPercent(sumaCoeficiente)}
          detalle="Suma registrada"
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(16rem,280px)_minmax(0,1fr)]">
        <Card>
          <CardHeader title="Edificios" icon={<Building2 className="h-5 w-5" aria-hidden="true" />} />
          <CardBody className="space-y-4">
            {cargando ? (
              <SkeletonList rows={3} label="Cargando edificios" />
            ) : edificios.length === 0 ? (
              <EmptyState title="Sin edificios" description="Agrega un edificio para empezar." />
            ) : (
              <ul className="space-y-2">
                {edificios.map((edificio) => {
                  const cantidad = departamentos.filter((departamento) => (
                    departamento.edificioId === edificio.id
                  )).length;
                  return (
                    <li key={edificio.id}>
                      <button
                        type="button"
                        aria-current={edificioActivo === edificio.id ? "true" : undefined}
                        onClick={() => setEdificioActivo(edificio.id)}
                        className={cn(
                          "flex min-h-11 w-full items-center justify-between rounded-lg",
                          "border px-3 text-left text-sm",
                          edificioActivo === edificio.id
                            ? "border-info-200 bg-info-50 text-info-800"
                            : "border-line hover:bg-canvas",
                        )}
                      >
                        <span>{edificio.nombre}</span>
                        <Badge tone="neutral">{cantidad}</Badge>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            {!soloLectura && (
              <form onSubmit={crearEdificio} className="space-y-3 border-t border-line pt-4">
                <Field label="Nuevo edificio" required>
                  <Input
                    value={nuevoEdificio}
                    onChange={(event) => setNuevoEdificio(event.target.value)}
                    placeholder="Ej. Torre Norte"
                  />
                </Field>
                <Button
                  type="submit"
                  variant="secondary"
                  fullWidth
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
              title={edificioSeleccionado?.nombre ?? "Estructura"}
              description="Los números de departamento no se repiten dentro del edificio."
              actions={(
                <Button
                  type="button"
                  variant="secondary"
                  onClick={exportarDepartamentos}
                  icon={<Download className="h-4 w-4" aria-hidden="true" />}
                >
                  Exportar
                </Button>
              )}
            />
            <CardBody>
              {!soloLectura && (
                <form onSubmit={crearDepartamento} className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  <Field label="Número" required>
                    <Input value={numero} onChange={(event) => setNumero(event.target.value)} />
                  </Field>
                  <Field label="Piso" required>
                    <Input
                      inputMode="numeric"
                      value={piso}
                      onChange={(event) => setPiso(event.target.value)}
                    />
                  </Field>
                  <Field label="Coeficiente (%)" required>
                    <Input
                      inputMode="decimal"
                      value={coeficiente}
                      onChange={(event) => setCoeficiente(event.target.value)}
                      placeholder="0.7200"
                    />
                  </Field>
                  <Button
                    className="self-end"
                    type="submit"
                    icon={<Plus className="h-4 w-4" aria-hidden="true" />}
                  >
                    Registrar
                  </Button>
                </form>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Departamentos registrados"
              description={
                `${departamentosDelEdificio.length} resultados · ${edificioSeleccionado?.nombre ?? ""}`
              }
              actions={(
                <Field label="Buscar departamento" className="w-full sm:w-64">
                  <Input
                    value={busqueda}
                    onChange={(event) => setBusqueda(event.target.value)}
                    placeholder="Número de departamento"
                    aria-label="Buscar departamento"
                  />
                </Field>
              )}
            />
            <CardBody>
              {cargando ? (
                <SkeletonList rows={5} label="Cargando departamentos" />
              ) : departamentosDelEdificio.length === 0 ? (
                <EmptyState
                  icon={Search}
                  title="No hay resultados"
                  description="No hay departamentos que coincidan con la búsqueda."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[560px] text-sm">
                    <caption className="sr-only">
                      Departamentos registrados en el edificio seleccionado
                    </caption>
                    <thead>
                      <tr className="border-b border-line text-left">
                        <th scope="col" className="p-3">Departamento</th>
                        <th scope="col" className="p-3">Piso</th>
                        <th scope="col" className="p-3">Edificio</th>
                        <th scope="col" className="p-3 text-right">Coeficiente</th>
                        <th scope="col" className="p-3">Estado</th>
                      </tr>
                    </thead>
                    <tbody>
                      {departamentosDelEdificio.map((departamento) => (
                        <tr key={departamento.id} className="border-b border-line">
                          <th scope="row" className="p-3 text-left">{departamento.numero}</th>
                          <td className="p-3">{departamento.piso}</td>
                          <td className="p-3">{edificioSeleccionado?.nombre}</td>
                          <td className="p-3 text-right tabular-nums">
                            {formatPercent(departamento.coeficiente)}
                          </td>
                          <td className="p-3"><Badge tone="success">Activo</Badge></td>
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
                title="Importación masiva"
                description="Carga un CSV y revisa los errores antes de importar los datos."
                icon={<FileSpreadsheet className="h-5 w-5" aria-hidden="true" />}
                actions={(
                  <Button type="button" variant="secondary" onClick={descargarPlantilla}>
                    Descargar plantilla
                  </Button>
                )}
              />
              <CardBody className="space-y-4">
                <Field label="Seleccionar archivo CSV" hint="Columnas: numero, piso, edificio, coeficiente">
                  <Input
                    ref={inputArchivoRef}
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(event) => void seleccionarArchivo(event)}
                  />
                </Field>
                {filasImportacion.length > 0 && (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="font-medium">Vista previa: {nombreArchivo}</p>
                      <Badge tone={filasInvalidas === 0 ? "success" : "warning"}>
                        {filasValidas} válidas · {filasInvalidas} con error
                      </Badge>
                    </div>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[650px] text-sm">
                        <caption className="sr-only">Vista previa y validación de filas CSV</caption>
                        <thead>
                          <tr className="border-b border-line text-left">
                            <th scope="col" className="p-3">Número</th>
                            <th scope="col" className="p-3">Piso</th>
                            <th scope="col" className="p-3">Edificio</th>
                            <th scope="col" className="p-3 text-right">Coeficiente</th>
                            <th scope="col" className="p-3">Validación</th>
                          </tr>
                        </thead>
                        <tbody>
                          {filasImportacion.map((fila, indice) => (
                            <tr
                              key={`${fila.edificio}-${fila.numero}-${indice}`}
                              className="border-b border-line"
                            >
                              <th scope="row" className="p-3 text-left">{fila.numero || "—"}</th>
                              <td className="p-3">{fila.piso || "—"}</td>
                              <td className="p-3">{fila.edificio || "—"}</td>
                              <td className="p-3 text-right tabular-nums">
                                {formatPercent(fila.coeficiente)}
                              </td>
                              <td className="p-3">
                                {fila.errores.length ? fila.errores.join(" · ") : "Fila válida"}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <Button
                      type="button"
                      disabled={filasValidas === 0}
                      onClick={confirmarImportacion}
                      icon={<Upload className="h-4 w-4" aria-hidden="true" />}
                    >
                      Importar filas válidas
                    </Button>
                  </div>
                )}
              </CardBody>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}

function Indicador({ title, valor, detalle }: { title: string; valor: string; detalle: string }) {
  return (
    <Card>
      <CardBody>
        <p className="text-sm text-muted">{title}</p>
        <p className="mt-1 text-2xl font-semibold tabular-nums">{valor}</p>
        <p className="mt-1 text-xs text-muted">{detalle}</p>
      </CardBody>
    </Card>
  );
}

export default EstructuraCondominio;
