"use client";

import { useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import {
  cambiarEstadoArea, configurarArea, listarCatalogoAreas, listarEdificios, registrarArea,
  type AreaComun, type ConfigurarAreaPayload, type Edificio,
} from "@/lib/api";
import { formatMoney, normalizeMoney } from "@/lib/money";

interface Props { condominioId: string | null; soloLectura: boolean }
const VACIO = { nombre: "", descripcion: "", edificio_id: "", aforo_maximo: "12", costo_reserva: "0.00", hora_apertura: "08:00", hora_cierre: "22:00", tiempo_maximo_horas: "4" };
const POR_PAGINA = 50;

export function AreasSection({ condominioId, soloLectura }: Props) {
  const [areas, setAreas] = useState<AreaComun[]>([]);
  const [edificios, setEdificios] = useState<Edificio[]>([]);
  const [form, setForm] = useState(VACIO);
  const [editando, setEditando] = useState<AreaComun | null>(null);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [filtro, setFiltro] = useState("todas");
  const [pagina, setPagina] = useState(0);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    if (!condominioId) return;
    let vigente = true;
    setLoading(true);
    setError(null);
    Promise.all([
      listarCatalogoAreas(condominioId, filtro === "todas" ? undefined : filtro === "activas", POR_PAGINA, pagina * POR_PAGINA),
      listarEdificios(condominioId),
    ]).then(([catalogo, bloques]) => {
      if (vigente) { setAreas(catalogo); setEdificios(bloques); }
    }).catch((cause) => { if (vigente) setError(cause instanceof Error ? cause.message : "No se pudo cargar el catálogo."); })
      .finally(() => { if (vigente) setLoading(false); });
    return () => { vigente = false; };
  }, [condominioId, filtro, pagina, revision]);

  function editar(area: AreaComun) {
    setEditando(area);
    setForm({ nombre: area.nombre, descripcion: area.descripcion ?? "", edificio_id: area.edificio_id ?? "",
      aforo_maximo: String(area.aforo_maximo), costo_reserva: area.costo_reserva, hora_apertura: area.hora_apertura,
      hora_cierre: area.hora_cierre, tiempo_maximo_horas: String(area.tiempo_maximo_horas) });
    setMensaje(null);
    setError(null);
    document.getElementById("formulario-area")?.scrollIntoView({ behavior: "smooth", block: "center" });
  }

  async function guardar(event: FormEvent) {
    event.preventDefault();
    if (!condominioId || soloLectura || busy) return;
    setError(null);
    setMensaje(null);
    if (!/^\d{1,10}(?:\.\d{1,2})?$/.test(form.costo_reserva.trim())) {
      setError("Ingresa un costo no negativo con hasta dos decimales."); return;
    }
    if (form.hora_cierre <= form.hora_apertura) {
      setError("El cierre debe ser posterior a la apertura en el mismo día."); return;
    }
    const datos: ConfigurarAreaPayload = {
      nombre: form.nombre, descripcion: form.descripcion.trim() || null, edificio_id: form.edificio_id || null,
      aforo_maximo: Number(form.aforo_maximo), costo_reserva: normalizeMoney(form.costo_reserva),
      hora_apertura: form.hora_apertura, hora_cierre: form.hora_cierre, tiempo_maximo_horas: Number(form.tiempo_maximo_horas),
    };
    setBusy(true);
    try {
      const area = editando ? await configurarArea(condominioId, editando.id, datos) : await registrarArea(condominioId, datos);
      setMensaje(`Área «${area.nombre}» guardada en PostgreSQL. Tarifa por turno: ${formatMoney(area.costo_reserva, area.moneda)}.`);
      setEditando(null);
      setForm(VACIO);
      setFiltro("todas");
      setPagina(0);
      setRevision((value) => value + 1);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo guardar el área.");
    } finally { setBusy(false); }
  }

  async function cambiarEstado(area: AreaComun) {
    if (!condominioId || soloLectura || busy) return;
    setBusy(true);
    setError(null);
    setMensaje(null);
    try {
      const actualizado = await cambiarEstadoArea(condominioId, area.id, !area.esta_activa);
      setMensaje(actualizado.esta_activa ? `Área «${area.nombre}» habilitada para nuevas reservas.` : `Área «${area.nombre}» desactivada. Sus reservas anteriores se conservan.`);
      setRevision((value) => value + 1);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "No se pudo cambiar el estado."); }
    finally { setBusy(false); }
  }

  if (!condominioId) return <Alert tone="info">Selecciona un condominio en Configuración para consultar sus áreas comunes.</Alert>;
  const moneda = editando?.moneda ?? areas[0]?.moneda;

  return (
    <div className="space-y-6">
      {error && <Alert tone="danger" title="No se completó la operación">{error}</Alert>}
      {mensaje && <Alert tone="success" title="Resultado del catálogo">{mensaje}</Alert>}
      {!soloLectura && <Card>
        <CardHeader title={editando ? "Editar área común" : "Registrar área común"} description="Horarios diarios en America/Lima. El costo corresponde a un turno y utiliza la moneda del condominio." />
        <CardBody>
          <form id="formulario-area" onSubmit={guardar} className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Nombre del área" required><Input value={form.nombre} maxLength={100} onChange={(e) => setForm({ ...form, nombre: e.target.value })} /></Field>
              <Field label="Edificio de uso exclusivo"><Select value={form.edificio_id} disabled={busy || loading} onChange={(e) => setForm({ ...form, edificio_id: e.target.value })}><option value="">Compartida por todo el condominio</option>{edificios.map((e) => <option key={e.id} value={e.id}>{e.nombre_bloque}</option>)}</Select></Field>
              <Field label="Aforo máximo" required><Input type="number" min={1} max={2147483647} step={1} value={form.aforo_maximo} onChange={(e) => setForm({ ...form, aforo_maximo: e.target.value })} /></Field>
              <Field label={`Costo por turno${moneda ? ` (${moneda})` : ""}`} required hint="En la moneda del condominio; 0.00 para uso gratuito."><Input inputMode="decimal" value={form.costo_reserva} maxLength={13} onChange={(e) => setForm({ ...form, costo_reserva: e.target.value.replace(",", ".") })} /></Field>
              <Field label="Hora de apertura" required><Input type="time" step={60} value={form.hora_apertura} onChange={(e) => setForm({ ...form, hora_apertura: e.target.value })} /></Field>
              <Field label="Hora de cierre" required><Input type="time" step={60} value={form.hora_cierre} onChange={(e) => setForm({ ...form, hora_cierre: e.target.value })} /></Field>
              <Field label="Duración máxima por reserva (horas)" required><Input type="number" min={1} max={24} step={1} value={form.tiempo_maximo_horas} onChange={(e) => setForm({ ...form, tiempo_maximo_horas: e.target.value })} /></Field>
            </div>
            <Field label="Descripción y condiciones de uso"><Textarea value={form.descripcion} maxLength={4000} onChange={(e) => setForm({ ...form, descripcion: e.target.value })} /></Field>
            <div className="flex flex-wrap gap-3"><Button type="submit" disabled={busy || loading} loading={busy}>{editando ? "Guardar cambios del área" : "Crear área común"}</Button>{editando && <Button variant="secondary" disabled={busy} onClick={() => { setEditando(null); setForm(VACIO); }}>Cancelar edición</Button>}</div>
          </form>
        </CardBody>
      </Card>}
      <Card>
        <CardHeader title="Catálogo de áreas comunes" description={soloLectura ? "Consulta de condiciones en modo solo lectura." : "Activar o desactivar controla nuevas reservas y conserva el historial."} />
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <Field label="Estado de las áreas"><Select value={filtro} disabled={busy || loading} onChange={(event) => { setFiltro(event.target.value); setPagina(0); }}><option value="todas">Todas</option><option value="activas">Activas</option><option value="inactivas">Inactivas</option></Select></Field>
            <Button variant="secondary" disabled={busy || loading} onClick={() => setRevision((value) => value + 1)}>Actualizar catálogo</Button>
          </div>
          {loading ? <p role="status">Cargando áreas comunes…</p> : areas.length === 0 ? <p>No hay áreas comunes en esta página.</p> : <div className="grid gap-4 xl:grid-cols-2">{areas.map((area) => (
            <article key={area.id} className="space-y-3 rounded-xl border border-line bg-canvas p-4">
              <div className="flex flex-wrap items-start justify-between gap-2"><h3 className="min-w-0 break-words font-semibold">{area.nombre}</h3><Badge tone={area.esta_activa ? "success" : "neutral"}>{area.esta_activa ? "Activa" : "Inactiva"}</Badge></div>
              {area.descripcion && <p className="whitespace-pre-wrap break-words text-sm text-muted">{area.descripcion}</p>}
              <dl className="space-y-1 text-sm"><div><dt className="inline font-medium">Tarifa por turno: </dt><dd className="inline">{formatMoney(area.costo_reserva, area.moneda)}</dd></div><div><dt className="inline font-medium">Aforo: </dt><dd className="inline">{area.aforo_maximo} personas</dd></div><div><dt className="inline font-medium">Horario diario: </dt><dd className="inline">{area.hora_apertura}–{area.hora_cierre} · Lima</dd></div><div><dt className="inline font-medium">Duración máxima: </dt><dd className="inline">{area.tiempo_maximo_horas} horas</dd></div><div><dt className="inline font-medium">Acceso: </dt><dd className="inline">{area.edificio_nombre ?? "Compartida por todo el condominio"}</dd></div></dl>
              {!soloLectura && <div className="flex flex-wrap gap-2"><Button size="sm" variant="secondary" disabled={busy} onClick={() => editar(area)} aria-label={`Editar área ${area.nombre}`}>Editar área</Button><Button size="sm" variant="ghost" disabled={busy} onClick={() => void cambiarEstado(area)} aria-label={`${area.esta_activa ? "Desactivar" : "Activar"} área ${area.nombre}`}>{area.esta_activa ? "Desactivar área" : "Activar área"}</Button></div>}
            </article>
          ))}</div>}
          <div className="flex items-center justify-between gap-3"><Button variant="secondary" disabled={pagina === 0 || loading || busy} onClick={() => setPagina((value) => value - 1)}>Anterior</Button><span className="text-sm text-muted">Página {pagina + 1}</span><Button variant="secondary" disabled={areas.length < POR_PAGINA || loading || busy} onClick={() => setPagina((value) => value + 1)}>Siguiente</Button></div>
        </CardBody>
      </Card>
    </div>
  );
}
