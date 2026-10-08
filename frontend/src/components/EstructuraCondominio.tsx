"use client";

import { ChangeEvent, FormEvent, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  Building2,
  CheckCircle2,
  FileSpreadsheet,
  Plus,
  Search,
  Upload,
  X,
} from "lucide-react";
import { Departamento } from "@/lib/api";

type Edificio = {
  id: string;
  nombre: string;
};

type DepartamentoEstructura = Departamento & {
  id: string;
  edificioId: string;
};

type FilaImportacion = {
  numero: string;
  piso: number;
  edificio: string;
  coeficiente: string;
  errores: string[];
};

type Feedback = {
  tipo: "exito" | "error";
  mensaje: string;
};

const EDIFICIO_INICIAL: Edificio = { id: "edificio-3", nombre: "Edificio 3" };

function normalizarCoeficiente(valor: string) {
  const numero = Number(valor.replace(",", "."));
  return Number.isFinite(numero) ? numero.toFixed(4) : valor;
}

function escaparCsv(valor: string | number) {
  const texto = String(valor);
  return texto.includes(",") ? `"${texto.replace(/"/g, '""')}"` : texto;
}

export default function EstructuraCondominio({
  departamentosIniciales,
  soloLectura = false,
}: {
  departamentosIniciales: Departamento[];
  soloLectura?: boolean;
}) {
  const datosInicialesCargados = useRef(departamentosIniciales.length > 0);
  const [edificios, setEdificios] = useState<Edificio[]>([EDIFICIO_INICIAL]);
  const [departamentos, setDepartamentos] = useState<DepartamentoEstructura[]>(() =>
    departamentosIniciales.map((departamento, indice) => ({
      ...departamento,
      id: `departamento-${indice + 1}`,
      edificioId: EDIFICIO_INICIAL.id,
    }))
  );
  const [edificioActivo, setEdificioActivo] = useState(EDIFICIO_INICIAL.id);
  const [nuevoEdificio, setNuevoEdificio] = useState("");
  const [numero, setNumero] = useState("");
  const [piso, setPiso] = useState("");
  const [coeficiente, setCoeficiente] = useState("");
  const [busqueda, setBusqueda] = useState("");
  const [feedback, setFeedback] = useState<Feedback | null>(null);
  const [filasImportacion, setFilasImportacion] = useState<FilaImportacion[]>([]);
  const [nombreArchivo, setNombreArchivo] = useState("");
  const inputArchivoRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (datosInicialesCargados.current || departamentosIniciales.length === 0) return;
    setDepartamentos(
      departamentosIniciales.map((departamento, indice) => ({
        ...departamento,
        id: `departamento-${indice + 1}`,
        edificioId: EDIFICIO_INICIAL.id,
      }))
    );
    datosInicialesCargados.current = true;
  }, [departamentosIniciales]);

  const edificioSeleccionado = edificios.find((edificio) => edificio.id === edificioActivo);
  const departamentosEdificio = useMemo(
    () =>
      departamentos.filter(
        (departamento) =>
          departamento.edificioId === edificioActivo &&
          departamento.numero.toLowerCase().includes(busqueda.trim().toLowerCase())
      ),
    [busqueda, departamentos, edificioActivo]
  );

  const coeficienteTotal = departamentos
    .filter((departamento) => departamento.edificioId === edificioActivo)
    .reduce((total, departamento) => total + Number(departamento.coeficiente), 0);

  function crearEdificio(evento: FormEvent) {
    evento.preventDefault();
    if (soloLectura) return;
    const nombre = nuevoEdificio.trim();
    if (!nombre) return;
    if (edificios.some((edificio) => edificio.nombre.toLowerCase() === nombre.toLowerCase())) {
      setFeedback({ tipo: "error", mensaje: "Ya existe un edificio con ese nombre." });
      return;
    }

    const edificio = { id: `edificio-${Date.now()}`, nombre };
    setEdificios((actuales) => [...actuales, edificio]);
    setEdificioActivo(edificio.id);
    setNuevoEdificio("");
    setFeedback({ tipo: "exito", mensaje: `${nombre} fue registrado correctamente.` });
  }

  function crearDepartamento(evento: FormEvent) {
    evento.preventDefault();
    if (soloLectura) return;
    const numeroLimpio = numero.trim();
    const pisoNumerico = Number(piso);
    const coeficienteNumerico = Number(coeficiente.replace(",", "."));

    if (!numeroLimpio || !piso.trim() || !Number.isInteger(pisoNumerico) || pisoNumerico < 1) {
      setFeedback({ tipo: "error", mensaje: "Ingresa un número de departamento y un piso válido." });
      return;
    }
    if (!Number.isFinite(coeficienteNumerico) || coeficienteNumerico <= 0 || coeficienteNumerico > 100) {
      setFeedback({ tipo: "error", mensaje: "El coeficiente debe ser mayor que 0 y menor o igual que 100." });
      return;
    }
    if (
      departamentos.some(
        (departamento) =>
          departamento.edificioId === edificioActivo &&
          departamento.numero.toLowerCase() === numeroLimpio.toLowerCase()
      )
    ) {
      setFeedback({
        tipo: "error",
        mensaje: `El departamento ${numeroLimpio} ya existe en ${edificioSeleccionado?.nombre}.`,
      });
      return;
    }

    setDepartamentos((actuales) => [
      ...actuales,
      {
        id: `departamento-${Date.now()}`,
        edificioId: edificioActivo,
        numero: numeroLimpio,
        piso: pisoNumerico,
        coeficiente: coeficienteNumerico.toFixed(4),
        saldo_a_favor: "0.00",
        estado_financiero: "AL_DIA",
        deuda_vencida: "0.00",
      },
    ]);
    setNumero("");
    setPiso("");
    setCoeficiente("");
    setFeedback({ tipo: "exito", mensaje: `Departamento ${numeroLimpio} registrado correctamente.` });
  }

  function validarFilaImportacion(columnas: string[], numeroFila: number): FilaImportacion {
    const [numeroCsv = "", pisoCsv = "", edificioCsv = "", coeficienteCsv = ""] = columnas.map((valor) =>
      valor.trim()
    );
    const errores: string[] = [];
    const pisoNumerico = Number(pisoCsv);
    const coeficienteNumerico = Number(coeficienteCsv.replace(",", "."));

    if (!numeroCsv) errores.push(`Fila ${numeroFila}: falta el número`);
    if (!pisoCsv || !Number.isInteger(pisoNumerico) || pisoNumerico < 1) errores.push(`Fila ${numeroFila}: piso inválido`);
    if (!edificioCsv) errores.push(`Fila ${numeroFila}: falta el edificio`);
    if (!Number.isFinite(coeficienteNumerico) || coeficienteNumerico <= 0 || coeficienteNumerico > 100) {
      errores.push(`Fila ${numeroFila}: coeficiente inválido`);
    }

    const edificioExistente = edificios.find(
      (edificio) => edificio.nombre.toLowerCase() === edificioCsv.toLowerCase()
    );
    if (
      edificioExistente &&
      departamentos.some(
        (departamento) =>
          departamento.edificioId === edificioExistente.id &&
          departamento.numero.toLowerCase() === numeroCsv.toLowerCase()
      )
    ) {
      errores.push(`Fila ${numeroFila}: departamento duplicado`);
    }

    return {
      numero: numeroCsv,
      piso: pisoNumerico,
      edificio: edificioCsv,
      coeficiente: normalizarCoeficiente(coeficienteCsv),
      errores,
    };
  }

  async function seleccionarArchivo(evento: ChangeEvent<HTMLInputElement>) {
    if (soloLectura) return;
    const archivo = evento.target.files?.[0];
    if (!archivo) return;
    setNombreArchivo(archivo.name);
    setFeedback(null);

    const texto = await archivo.text();
    const lineas = texto
      .split(/\r?\n/)
      .map((linea) => linea.trim())
      .filter(Boolean);
    const primeraFilaEsCabecera = lineas[0]?.toLowerCase().includes("numero");
    const datos = primeraFilaEsCabecera ? lineas.slice(1) : lineas;
    const filas = datos.map((linea, indice) => {
      const separador = linea.includes(";") ? ";" : ",";
      return validarFilaImportacion(linea.split(separador), indice + (primeraFilaEsCabecera ? 2 : 1));
    });

    const claves = new Set<string>();
    filas.forEach((fila, indice) => {
      const clave = `${fila.edificio.toLowerCase()}::${fila.numero.toLowerCase()}`;
      if (claves.has(clave)) filas[indice].errores.push("Duplicado dentro del archivo");
      claves.add(clave);
    });
    setFilasImportacion(filas);
  }

  function confirmarImportacion() {
    if (soloLectura) return;
    const filasValidas = filasImportacion.filter((fila) => fila.errores.length === 0);
    const filasInvalidas = filasImportacion.filter((fila) => fila.errores.length > 0);
    if (!filasValidas.length) return;

    const nuevosEdificios = [...edificios];
    const nuevosDepartamentos: DepartamentoEstructura[] = [];
    filasValidas.forEach((fila, indice) => {
      let edificio = nuevosEdificios.find(
        (actual) => actual.nombre.toLowerCase() === fila.edificio.toLowerCase()
      );
      if (!edificio) {
        edificio = { id: `edificio-importado-${Date.now()}-${indice}`, nombre: fila.edificio };
        nuevosEdificios.push(edificio);
      }
      nuevosDepartamentos.push({
        id: `departamento-importado-${Date.now()}-${indice}`,
        edificioId: edificio.id,
        numero: fila.numero,
        piso: fila.piso,
        coeficiente: fila.coeficiente,
        saldo_a_favor: "0.00",
        estado_financiero: "AL_DIA",
        deuda_vencida: "0.00",
      });
    });

    setEdificios(nuevosEdificios);
    setDepartamentos((actuales) => [...actuales, ...nuevosDepartamentos]);
    setFilasImportacion(filasInvalidas);
    if (filasInvalidas.length === 0) {
      setNombreArchivo("");
      if (inputArchivoRef.current) inputArchivoRef.current.value = "";
    }
    setFeedback({
      tipo: "exito",
      mensaje: filasInvalidas.length
        ? `${nuevosDepartamentos.length} departamentos válidos fueron importados. ${filasInvalidas.length} filas con errores no fueron procesadas.`
        : `${nuevosDepartamentos.length} departamentos fueron importados.`,
    });
  }

  function descargarPlantilla() {
    const contenido = [
      "numero,piso,edificio,coeficiente",
      "101,1,Torre Norte,0.7200",
      "102,1,Torre Norte,0.6800",
    ].join("\n");
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(new Blob([contenido], { type: "text/csv;charset=utf-8" }));
    enlace.download = "plantilla-departamentos.csv";
    enlace.click();
    URL.revokeObjectURL(enlace.href);
  }

  function exportarDepartamentos() {
    const filas = departamentos.map((departamento) => [
      departamento.numero,
      departamento.piso,
      edificios.find((edificio) => edificio.id === departamento.edificioId)?.nombre ?? "",
      departamento.coeficiente,
    ]);
    const contenido = ["numero,piso,edificio,coeficiente", ...filas.map((fila) => fila.map(escaparCsv).join(","))].join(
      "\n"
    );
    const enlace = document.createElement("a");
    enlace.href = URL.createObjectURL(new Blob([contenido], { type: "text/csv;charset=utf-8" }));
    enlace.download = "estructura-condominio.csv";
    enlace.click();
    URL.revokeObjectURL(enlace.href);
  }

  const cantidadFilasValidas = filasImportacion.filter((fila) => fila.errores.length === 0).length;
  const cantidadFilasInvalidas = filasImportacion.length - cantidadFilasValidas;

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Edificios</p>
          <p className="mt-1 text-3xl font-black text-slate-900">{edificios.length}</p>
          <p className="mt-1 text-xs text-slate-500">Estructuras registradas</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Departamentos</p>
          <p className="mt-1 text-3xl font-black text-slate-900">{departamentos.length}</p>
          <p className="mt-1 text-xs text-slate-500">Unidades inmobiliarias</p>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Coeficiente del edificio</p>
          <p className="mt-1 text-3xl font-black text-blue-700">{coeficienteTotal.toFixed(4)}%</p>
          <p className="mt-1 text-xs text-slate-500">Suma de alícuotas registradas</p>
        </div>
      </div>

      {feedback && (
        <div
          role="status"
          className={`flex items-start justify-between gap-3 rounded-xl border p-4 text-sm ${
            feedback.tipo === "exito"
              ? "border-emerald-200 bg-emerald-50 text-emerald-800"
              : "border-rose-200 bg-rose-50 text-rose-800"
          }`}
        >
          <div className="flex items-start gap-2">
            {feedback.tipo === "exito" ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
            ) : (
              <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            )}
            <span>{feedback.mensaje}</span>
          </div>
          <button aria-label="Cerrar mensaje" onClick={() => setFeedback(null)}>
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {soloLectura && (
        <div className="rounded-xl border border-purple-200 bg-purple-50 p-4 text-sm text-purple-800">
          <p className="font-bold">Modo auditoría: solo lectura</p>
          <p className="mt-1 text-xs">Puede consultar y exportar la estructura, pero no registrar edificios, departamentos ni importaciones.</p>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[280px_1fr]">
        <aside className="space-y-4 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div>
            <h2 className="flex items-center gap-2 font-bold text-slate-900">
              <Building2 className="h-5 w-5 text-blue-600" /> Edificios
            </h2>
            <p className="mt-1 text-xs text-slate-500">Selecciona una estructura para administrar sus unidades.</p>
          </div>

          <div className="space-y-2">
            {edificios.map((edificio) => {
              const cantidad = departamentos.filter((departamento) => departamento.edificioId === edificio.id).length;
              return (
                <button
                  key={edificio.id}
                  onClick={() => setEdificioActivo(edificio.id)}
                  className={`flex w-full items-center justify-between rounded-xl border px-3 py-2.5 text-left text-sm transition-colors ${
                    edificioActivo === edificio.id
                      ? "border-blue-200 bg-blue-50 font-bold text-blue-800"
                      : "border-transparent text-slate-600 hover:bg-slate-50"
                  }`}
                >
                  <span>{edificio.nombre}</span>
                  <span className="rounded-full bg-white px-2 py-0.5 text-[10px] text-slate-500 shadow-sm">{cantidad}</span>
                </button>
              );
            })}
          </div>

          {!soloLectura && <form onSubmit={crearEdificio} className="space-y-2 border-t border-slate-100 pt-4">
            <label className="text-xs font-semibold text-slate-700" htmlFor="nombre-edificio">
              Nuevo edificio
            </label>
            <input
              id="nombre-edificio"
              value={nuevoEdificio}
              onChange={(evento) => setNuevoEdificio(evento.target.value)}
              placeholder="Ej. Torre Norte"
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
            />
            <button className="flex w-full items-center justify-center gap-2 rounded-lg bg-slate-900 px-3 py-2 text-xs font-bold text-white hover:bg-slate-800">
              <Plus className="h-4 w-4" /> Agregar edificio
            </button>
          </form>}
        </aside>

        <section className="space-y-6">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wide text-blue-600">Estructura seleccionada</p>
                <h2 className="mt-1 text-xl font-bold text-slate-900">{edificioSeleccionado?.nombre}</h2>
                <p className="text-xs text-slate-500">Los números no pueden repetirse dentro de este edificio.</p>
              </div>
              <button
                type="button"
                onClick={exportarDepartamentos}
                className="flex items-center justify-center gap-2 rounded-xl border border-slate-300 px-4 py-2.5 text-xs font-bold text-slate-700 hover:bg-slate-50"
              >
                <FileSpreadsheet className="h-4 w-4" /> Exportar estructura
              </button>
            </div>

            {!soloLectura && <form onSubmit={crearDepartamento} className="mt-5 grid gap-3 border-t border-slate-100 pt-5 sm:grid-cols-2 lg:grid-cols-[1fr_0.7fr_1fr_auto]">
              <label className="text-xs font-semibold text-slate-700">
                Número
                <input
                  value={numero}
                  onChange={(evento) => setNumero(evento.target.value)}
                  placeholder="Ej. 1501"
                  className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </label>
              <label className="text-xs font-semibold text-slate-700">
                Piso
                <input
                  type="number"
                  min="1"
                  value={piso}
                  onChange={(evento) => setPiso(evento.target.value)}
                  placeholder="15"
                  className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </label>
              <label className="text-xs font-semibold text-slate-700">
                Coeficiente (%)
                <input
                  inputMode="decimal"
                  value={coeficiente}
                  onChange={(evento) => setCoeficiente(evento.target.value)}
                  placeholder="0.7200"
                  className="mt-1.5 w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm font-normal outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </label>
              <button className="mt-auto flex h-[42px] items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-xs font-bold text-white hover:bg-blue-700">
                <Plus className="h-4 w-4" /> Registrar
              </button>
            </form>}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-col gap-3 border-b border-slate-200 p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="font-bold text-slate-900">Departamentos registrados</h3>
                <p className="text-xs text-slate-500">{departamentosEdificio.length} resultados en {edificioSeleccionado?.nombre}</p>
              </div>
              <label className="relative block sm:w-64">
                <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
                <input
                  value={busqueda}
                  onChange={(evento) => setBusqueda(evento.target.value)}
                  placeholder="Buscar departamento"
                  className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </label>
            </div>
            <div className="max-h-[420px] overflow-auto">
              <table className="w-full min-w-[560px] text-left text-xs">
                <thead className="sticky top-0 bg-slate-50 text-slate-500">
                  <tr>
                    <th className="px-5 py-3 font-semibold">Departamento</th>
                    <th className="px-5 py-3 font-semibold">Piso</th>
                    <th className="px-5 py-3 font-semibold">Edificio</th>
                    <th className="px-5 py-3 font-semibold">Coeficiente</th>
                    <th className="px-5 py-3 font-semibold">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {departamentosEdificio.map((departamento) => (
                    <tr key={departamento.id} className="hover:bg-slate-50">
                      <td className="px-5 py-3 font-bold text-slate-900">Dpto. {departamento.numero}</td>
                      <td className="px-5 py-3 text-slate-600">{departamento.piso}</td>
                      <td className="px-5 py-3 text-slate-600">{edificioSeleccionado?.nombre}</td>
                      <td className="px-5 py-3 font-mono text-slate-700">{departamento.coeficiente}%</td>
                      <td className="px-5 py-3">
                        <span className="rounded-full bg-emerald-100 px-2 py-1 text-[10px] font-bold text-emerald-800">ACTIVO</span>
                      </td>
                    </tr>
                  ))}
                  {departamentosEdificio.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-5 py-10 text-center text-sm text-slate-400">
                        No hay departamentos que coincidan con la búsqueda.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {!soloLectura && <div className="rounded-2xl border border-dashed border-blue-300 bg-blue-50/50 p-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="flex items-center gap-2 font-bold text-slate-900">
                  <Upload className="h-5 w-5 text-blue-600" /> Importación masiva
                </h3>
                <p className="mt-1 text-xs text-slate-600">Carga un CSV y revisa los errores antes de registrar los datos.</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={descargarPlantilla} className="rounded-lg px-3 py-2 text-xs font-bold text-blue-700 hover:bg-blue-100">
                  Descargar plantilla
                </button>
                <label className="cursor-pointer rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white hover:bg-blue-700">
                  Seleccionar CSV
                  <input ref={inputArchivoRef} type="file" accept=".csv,text/csv" onChange={seleccionarArchivo} className="sr-only" />
                </label>
              </div>
            </div>

            {filasImportacion.length > 0 && (
              <div className="mt-5 overflow-hidden rounded-xl border border-slate-200 bg-white">
                <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
                  <div>
                    <p className="text-sm font-bold text-slate-900">Vista previa: {nombreArchivo}</p>
                    <p className="text-xs text-slate-500">{filasImportacion.length} filas encontradas</p>
                  </div>
                  <span className={`rounded-full px-2.5 py-1 text-[10px] font-bold ${cantidadFilasInvalidas === 0 ? "bg-emerald-100 text-emerald-800" : "bg-amber-100 text-amber-800"}`}>
                    {cantidadFilasValidas} VÁLIDAS · {cantidadFilasInvalidas} CON ERROR
                  </span>
                </div>
                <div className="max-h-64 overflow-auto">
                  <table className="w-full min-w-[650px] text-left text-xs">
                    <thead className="bg-slate-50 text-slate-500">
                      <tr>
                        <th className="px-4 py-2.5">Número</th><th className="px-4 py-2.5">Piso</th><th className="px-4 py-2.5">Edificio</th><th className="px-4 py-2.5">Coeficiente</th><th className="px-4 py-2.5">Validación</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filasImportacion.map((fila, indice) => (
                        <tr key={`${fila.edificio}-${fila.numero}-${indice}`}>
                          <td className="px-4 py-2.5 font-bold">{fila.numero || "—"}</td>
                          <td className="px-4 py-2.5">{Number.isNaN(fila.piso) ? "—" : fila.piso}</td>
                          <td className="px-4 py-2.5">{fila.edificio || "—"}</td>
                          <td className="px-4 py-2.5 font-mono">{fila.coeficiente}</td>
                          <td className={`px-4 py-2.5 ${fila.errores.length ? "text-rose-700" : "font-semibold text-emerald-700"}`}>
                            {fila.errores.length ? fila.errores.join(" · ") : "Fila válida"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex justify-end border-t border-slate-200 p-3">
                  <button
                    type="button"
                    disabled={cantidadFilasValidas === 0}
                    onClick={confirmarImportacion}
                    className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-slate-300"
                  >
                    Importar {cantidadFilasValidas} filas válidas
                  </button>
                </div>
              </div>
            )}
          </div>}
        </section>
      </div>
    </div>
  );
}
