"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useAuth } from "@/context/AuthContext";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import {
  ApiError, consultarReparto, listarDepartamentos, listarEdificios, previsualizarReparto, publicarReparto,
  type ConfiguracionReparto, type DepartamentoRegistrado, type RepartoIncidencia,
} from "@/lib/api";
import { formatMoney } from "@/lib/money";

export function RepartoCosto({ incidenciaId, costoId }: { incidenciaId: string; costoId: string }) {
  const { user } = useAuth();
  const [abierto, setAbierto] = useState(false);
  const [departamentos, setDepartamentos] = useState<DepartamentoRegistrado[]>([]);
  const [edificios, setEdificios] = useState<Record<string, string>>({});
  const [datos, setDatos] = useState<ConfiguracionReparto>({
    alcance: "TODOS", metodo: "EQUITATIVA", departamento_ids: [], concepto: "", motivo: "",
  });
  const [preview, setPreview] = useState<RepartoIncidencia | null>(null);
  const [publicado, setPublicado] = useState<RepartoIncidencia | null>(null);
  const [ocupada, setOcupada] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState("");
  const clave = useRef(crypto.randomUUID());

  useEffect(() => {
    if (!abierto || !user?.condominio_id) return;
    let vigente = true;
    setCargando(true);
    setError("");
    const cid = user.condominio_id;
    consultarReparto(incidenciaId, costoId).catch((causa) => {
        if (causa instanceof ApiError && causa.status === 404) return null;
        throw causa;
      }).then(async (reparto) => {
      if (!vigente) return;
      setPublicado(reparto);
      if (reparto) return;
      const [lista, bloques] = await Promise.all([listarDepartamentos(cid), listarEdificios(cid)]);
      if (!vigente) return;
      setDepartamentos(lista.filter((d) => d.activo));
      setEdificios(Object.fromEntries(bloques.map((e) => [e.id, e.nombre_bloque])));
    }).catch(() => { if (vigente) setError("No pudimos consultar el reparto y sus departamentos."); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, [abierto, user?.condominio_id, incidenciaId, costoId]);

  function cambiar(cambios: Partial<ConfiguracionReparto>) {
    setDatos((actual) => ({ ...actual, ...cambios }));
    setPreview(null);
    clave.current = crypto.randomUUID();
  }

  async function calcular(evento: FormEvent) {
    evento.preventDefault();
    setOcupada(true);
    setError("");
    try { setPreview(await previsualizarReparto(incidenciaId, costoId, datos)); }
    catch (causa) { setError(causa instanceof Error ? causa.message : "No pudimos calcular el reparto."); }
    finally { setOcupada(false); }
  }

  async function confirmar() {
    if (!preview) return;
    setOcupada(true);
    setError("");
    try { setPublicado(await publicarReparto(incidenciaId, costoId, datos, preview.huella, clave.current)); }
    catch (causa) { setError(causa instanceof Error ? causa.message : "No pudimos publicar los cargos."); }
    finally { setOcupada(false); }
  }

  const detalle = publicado || preview;
  return (
    <div className="mt-3 border-t border-line pt-3">
      <Button type="button" variant="secondary" onClick={() => setAbierto(!abierto)} aria-expanded={abierto}>
        {abierto ? "Ocultar reparto" : "Repartir / consultar este monto"}
      </Button>
      {abierto && (
        <div className="mt-3 space-y-3">
          {error && <Alert tone="danger">{error}</Alert>}
          {cargando ? <p role="status">Cargando reparto…</p> : (
            <>
              {!publicado && (
                <form onSubmit={calcular}>
                  <fieldset disabled={ocupada} className="space-y-3">
                    <Field label="Concepto público del cargo" required hint="No copies comentarios o información interna.">
                      <Input required maxLength={200} value={datos.concepto}
                        onChange={(e) => cambiar({ concepto: e.target.value })} />
                    </Field>
                    <Field label="Motivo de la publicación" required>
                      <Input required maxLength={500} value={datos.motivo}
                        onChange={(e) => cambiar({ motivo: e.target.value })} />
                    </Field>
                    <Field label="Departamentos participantes">
                      <Select value={datos.alcance} onChange={(e) => cambiar({
                        alcance: e.target.value as ConfiguracionReparto["alcance"], departamento_ids: [],
                      })}>
                        <option value="TODOS">Todos los departamentos activos</option>
                        <option value="SELECCIONADOS">Seleccionar departamentos</option>
                      </Select>
                    </Field>
                    {datos.alcance === "SELECCIONADOS" && (
                      <fieldset className="max-h-48 space-y-2 overflow-y-auto rounded border border-line p-3">
                        <legend className="text-sm font-medium">Unidades incluidas</legend>
                        {departamentos.map((d) => (
                          <label key={d.id} className="flex items-center gap-2">
                            <input type="checkbox" checked={datos.departamento_ids.includes(d.id)}
                              onChange={(e) => cambiar({ departamento_ids: e.target.checked
                                ? [...datos.departamento_ids, d.id] : datos.departamento_ids.filter((id) => id !== d.id) })} />
                            {edificios[d.edificio_id] || "Edificio"} · {d.numero} · {d.coeficiente_participacion} %
                          </label>
                        ))}
                      </fieldset>
                    )}
                    <Field label="Método de reparto">
                      <Select value={datos.metodo} onChange={(e) => cambiar({ metodo: e.target.value as ConfiguracionReparto["metodo"] })}>
                        <option value="EQUITATIVA">Partes iguales</option>
                        <option value="POR_ALICUOTA">Por alícuotas de los participantes</option>
                      </Select>
                    </Field>
                    <Button type="submit" loading={ocupada}>Previsualizar reparto</Button>
                  </fieldset>
                </form>
              )}
              {detalle && (
                <div className="space-y-2" aria-live="polite">
                  <p className="font-semibold">{publicado ? "Cargos publicados" : "Vista previa"} · {detalle.concepto}</p>
                  <p>{detalle.metodo === "EQUITATIVA" ? "Partes iguales" : "Por alícuotas"} · Total: {formatMoney(detalle.monto, detalle.moneda)}</p>
                  <ul className="max-h-60 space-y-1 overflow-y-auto">
                    {detalle.participantes.map((p) => (
                      <li key={p.departamento_id} className="flex justify-between gap-3">
                        <span>{p.edificio} · {p.numero}</span><span>{formatMoney(p.monto, detalle.moneda)}</span>
                      </li>
                    ))}
                  </ul>
                  {!publicado && <Button type="button" onClick={() => void confirmar()} loading={ocupada}>
                    Confirmar y publicar cargos
                  </Button>}
                  <p className="text-xs text-muted">Publicar genera cargos independientes. No se podrán editar ni borrar desde aquí.</p>
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}
