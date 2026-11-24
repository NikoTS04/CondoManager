import { useEffect, useRef, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input, Select, Textarea } from "@/components/ui/Field";
import {
  audienciaCorreo, confirmarComunicado, contactosSuprimidos, listarComunicados,
  operacionCorreo, politicaCorreo, previsualizarComunicado, reactivarContacto,
  resolverCorreoIncierto,
  type BorradorComunicado, type ContactoSuprimido, type DestinoComunicado,
  type NotificacionLog, type OperacionCorreo, type PoliticaCorreo,
} from "@/lib/api";
import { formatDate } from "@/lib/format";

export function ComunicadoEditor({ cid, onActualizada }: { cid: string; onActualizada: () => void }) {
  const [opciones, setOpciones] = useState<DestinoComunicado[]>([]);
  const [titulo, setTitulo] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [tipo, setTipo] = useState("todo");
  const [ids, setIds] = useState<string[]>([]);
  const [vista, setVista] = useState<BorradorComunicado | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cargando, setCargando] = useState(true);
  const [intentoCarga, setIntentoCarga] = useState(0);
  const montado = useRef(true);
  useEffect(() => {
    montado.current = true;
    let vigente = true;
    setCargando(true);
    audienciaCorreo(cid).then((datos) => {
      if (vigente) { setOpciones(datos); setError(null); }
    }).catch((e) => { if (vigente) setError(e.message); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; montado.current = false; };
  }, [cid, intentoCarga]);
  const elecciones = new Map<string, string>();
  for (const d of opciones) {
    if (tipo === "usuario_ids") elecciones.set(d.usuario_id, `${d.nombre} — ${d.email}`);
    if (tipo === "departamento_ids") elecciones.set(d.departamento_id, `Dpto. ${d.departamento}`);
    if (tipo === "edificio_ids") elecciones.set(d.edificio_id, d.edificio || d.edificio_id);
  }
  async function previsualizar(event: FormEvent) {
    event.preventDefault();
    if (busy || (tipo !== "todo" && ids.length === 0)) return;
    setBusy(true); setError(null);
    try {
      const datos = await previsualizarComunicado({
        condominio_id: cid, titulo, mensaje, ...(tipo === "todo" ? {} : { [tipo]: ids }),
      });
      if (montado.current) setVista(datos);
    } catch (e) { if (montado.current) setError(e instanceof Error ? e.message : "No se pudo previsualizar."); }
    finally { if (montado.current) setBusy(false); }
  }
  async function confirmar() {
    if (!vista || busy) return;
    setBusy(true); setError(null);
    try {
      const datos = await confirmarComunicado(vista.id);
      if (montado.current) { setVista(datos); onActualizada(); }
    } catch (e) {
      if (montado.current) setError(e instanceof Error ? e.message : "Respuesta incierta. Reintenta la misma confirmación.");
    } finally { if (montado.current) setBusy(false); }
  }
  return <div className="space-y-4">
    {error && <Alert tone="danger">{error}</Alert>}
    {cargando ? <p role="status">Cargando contactos…</p> :
      opciones.length === 0 && <Button variant="secondary" onClick={() => setIntentoCarga((v) => v + 1)}>Recargar contactos</Button>}
    <form onSubmit={previsualizar}>
      <fieldset disabled={busy || cargando} className="space-y-4" onChange={() => setVista(null)}>
        <Field label="Título" required><Input value={titulo} minLength={5} maxLength={150} onChange={(e) => setTitulo(e.target.value)} /></Field>
        <Field label="Mensaje" required><Textarea value={mensaje} minLength={10} maxLength={20000} rows={5} onChange={(e) => setMensaje(e.target.value)} /></Field>
        <Field label="Audiencia"><Select value={tipo} onChange={(e) => { setTipo(e.target.value); setIds([]); }}>
          <option value="todo">Todo el condominio</option>
          <option value="edificio_ids">Edificios</option>
          <option value="departamento_ids">Departamentos</option>
          <option value="usuario_ids">Usuarios específicos</option>
        </Select></Field>
        {tipo !== "todo" && <Field label="Destinatarios seleccionados" required hint="Selecciona una o varias opciones.">
          <Select multiple size={6} value={ids} onChange={(e) => setIds(Array.from(e.target.selectedOptions, (o) => o.value))}>
            {Array.from(elecciones).map(([id, label]) => <option key={id} value={id}>{label}</option>)}
          </Select>
        </Field>}
        <p className="text-sm text-muted">Solo correo. Se excluyen contactos suprimidos y se envía un aviso por usuario.</p>
        <Button type="submit" loading={busy} disabled={cargando || (tipo !== "todo" && ids.length === 0)}>Previsualizar audiencia</Button>
      </fieldset>
    </form>
    {vista && <section aria-label="Previsualización" className="space-y-3 rounded-lg border border-line p-4">
      <h3 className="font-semibold">{vista.contenido.titulo}</h3>
      <p className="whitespace-pre-wrap">{vista.contenido.mensaje}</p>
      <p><strong>{vista.cantidad}</strong> destinatarios elegibles</p>
      <ul className="max-h-60 overflow-auto text-sm">
        {vista.destinatarios.map((d) => <li key={d.usuario_id}>{d.nombre} · {d.email}</li>)}
      </ul>
      {vista.confirmado_en ? <Alert tone="success">Comunicado en cola. La entrega aún no está confirmada.</Alert> :
        <Button loading={busy} disabled={busy || vista.cantidad === 0} onClick={() => void confirmar()}>Confirmar envío a {vista.cantidad} usuarios</Button>}
      <p className="text-xs text-muted">La vista caduca a los 15 minutos. Ante una respuesta incierta, reintenta esta misma confirmación; no crees otro comunicado.</p>
    </section>}
  </div>;
}

export function ResolucionIncierta({ aviso, onActualizada }: { aviso: NotificacionLog; onActualizada: () => void }) {
  const [decision, setDecision] = useState<"ACEPTADO" | "NO_ACEPTADO" | "DESCARTAR">("DESCARTAR");
  const [referencia, setReferencia] = useState("");
  const [messageId, setMessageId] = useState("");
  const [confirmado, setConfirmado] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function resolver(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError(null);
    try {
      await resolverCorreoIncierto(aviso.id, {
        ciclo: aviso.ciclo, intento: aviso.intentos, decision, referencia,
        message_id: decision === "ACEPTADO" ? messageId : undefined,
        confirmar_no_aceptado: confirmado,
      });
      onActualizada();
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo resolver."); }
    finally { setBusy(false); }
  }
  return <form onSubmit={resolver} className="mt-3 space-y-3">
    <p className="text-sm">Revisa primero el intento en Mailjet. No se reenvía automáticamente.</p>
    {error && <Alert tone="danger">{error}</Alert>}
    <fieldset disabled={busy} className="space-y-3">
      <Field label="Resultado de revisión"><Select value={decision} onChange={(e) => { setDecision(e.target.value as typeof decision); setConfirmado(false); }}>
        <option value="DESCARTAR">Descartar sin reenviar</option>
        <option value="ACEPTADO">Mailjet confirmó aceptación</option>
        <option value="NO_ACEPTADO">No aceptado: autorizar nuevo ciclo</option>
      </Select></Field>
      {decision === "ACEPTADO" && <Field label="MessageID verificado" required><Input value={messageId} pattern="[1-9][0-9]*" onChange={(e) => setMessageId(e.target.value)} /></Field>}
      <Field label="Referencia y motivo de la revisión" required hint="Identifica la evidencia revisada; no incluyas claves ni enlaces de activación.">
        <Textarea minLength={10} maxLength={500} value={referencia} onChange={(e) => setReferencia(e.target.value)} />
      </Field>
      {decision === "NO_ACEPTADO" && <label className="flex gap-2 text-sm">
        <input type="checkbox" required checked={confirmado} onChange={(e) => setConfirmado(e.target.checked)} />
        Verifiqué que Mailjet no aceptó este intento y autorizo otro ciclo de envío.
      </label>}
      <Button type="submit" loading={busy}>Registrar resolución auditada</Button>
    </fieldset>
  </form>;
}

export function CorreoOperacion({ cid, isAuditor }: { cid: string; isAuditor: boolean }) {
  const [lotes, setLotes] = useState<BorradorComunicado[]>([]);
  const [politica, setPolitica] = useState<PoliticaCorreo | null>(null);
  const [dias, setDias] = useState("");
  const [bloqueados, setBloqueados] = useState<ContactoSuprimido[]>([]);
  const [operacion, setOperacion] = useState<OperacionCorreo | null>(null);
  const [email, setEmail] = useState("");
  const [motivo, setMotivo] = useState("");
  const [version, setVersion] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [cargando, setCargando] = useState(true);
  useEffect(() => {
    let vigente = true;
    setCargando(true);
    Promise.all([listarComunicados(cid), politicaCorreo(cid), contactosSuprimidos(cid), operacionCorreo(cid)])
      .then(([l, p, b, o]) => {
        if (!vigente) return;
        setLotes(l); setPolitica(p); setDias(p.dias.join(",")); setBloqueados(b); setOperacion(o); setError(null);
      }).catch((e) => { if (vigente) setError(e.message); })
      .finally(() => { if (vigente) setCargando(false); });
    return () => { vigente = false; };
  }, [cid, version]);
  async function guardar(event: FormEvent) {
    event.preventDefault();
    if (busy || !politica) return;
    const valores = dias.split(",").map((d) => d.trim());
    if (valores.some((d) => !/^(0|[1-9][0-9]?)$/.test(d))) { setError("Indica días enteros separados por comas."); return; }
    setBusy(true); setError(null);
    try {
      await politicaCorreo(cid, { ...politica, dias: valores.map(Number) });
      setFeedback("Política guardada. Horario local de Lima."); setVersion((v) => v + 1);
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo guardar."); }
    finally { setBusy(false); }
  }
  async function reactivar(event: FormEvent) {
    event.preventDefault(); if (busy) return;
    setBusy(true); setError(null);
    try {
      await reactivarContacto(cid, email, motivo);
      setEmail(""); setMotivo(""); setFeedback("Contacto reactivado. No se reenvían avisos históricos."); setVersion((v) => v + 1);
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo reactivar."); }
    finally { setBusy(false); }
  }
  async function retomar(id: string) {
    if (busy) return;
    setBusy(true); setError(null);
    try {
      await confirmarComunicado(id);
      setFeedback("Confirmación recuperada. El mismo lote no se duplica.");
      setVersion((v) => v + 1);
    } catch (e) { setError(e instanceof Error ? e.message : "No se pudo confirmar el lote."); }
    finally { setBusy(false); }
  }
  return <Card className="xl:col-span-2">
    <CardHeader title="Operación de correo" description="Lotes, recordatorios y protección de contactos." />
    <CardBody className="space-y-6">
      <Button variant="secondary" disabled={busy || cargando} onClick={() => setVersion((v) => v + 1)}>Actualizar operación y lotes</Button>
      {cargando && <p role="status">Consultando operación…</p>}
      {error && <Alert tone="danger">{error}</Alert>}
      {feedback && <Alert tone="success">{feedback}</Alert>}
      {operacion && <section className="space-y-2">
        <h3 className="font-semibold">Supervisión</h3>
        <p>Proveedor {operacion.habilitado ? "habilitado" : "suspendido"} · {operacion.inciertos} inciertos · {operacion.alertas_abiertas} alertas abiertas.</p>
        <p>Último job: {operacion.job ? `${operacion.job.estado} · ${formatDate(operacion.job.fin || operacion.job.inicio)}` : "Sin ejecución registrada"}</p>
        {operacion.pendiente_desde && <p>Cola pendiente desde {formatDate(operacion.pendiente_desde)}</p>}
        {operacion.requiere_revision && <Alert tone="warning">Revisar programador: no existe una ejecución completa reciente.</Alert>}
        {operacion.cola_atrasada && <Alert tone="warning">Hay avisos pendientes desde hace más de 15 minutos. Revisa capacidad, proveedor y cola.</Alert>}
      </section>}
      <section className="space-y-3">
        <h3 className="font-semibold">Últimos 50 comunicados</h3>
        {!cargando && lotes.length === 0 && <p>No hay lotes registrados.</p>}
        <ul className="divide-y divide-line">{lotes.map((l) => <li key={l.id} className="py-3">
          <p className="font-medium">{l.contenido.titulo} · {l.cantidad} usuarios</p>
          <p className="text-sm">{l.confirmado_en ? `Confirmado ${formatDate(l.confirmado_en)}` : "Borrador sin confirmar"}</p>
          <p className="text-sm">{Object.entries(l.conteos || {}).map(([e, n]) => `${e}: ${n}`).join(" · ")}</p>
          {!isAuditor && !l.confirmado_en && <details className="mt-2">
            <summary className="cursor-pointer text-sm">Revisar borrador y recuperar confirmación</summary>
            <p className="my-3 whitespace-pre-wrap">{l.contenido.mensaje}</p>
            <ul className="max-h-60 overflow-auto text-sm">{l.destinatarios.map((d) => <li key={d.usuario_id}>{d.nombre} · {d.email}</li>)}</ul>
            <Button disabled={busy || l.cantidad === 0} onClick={() => void retomar(l.id)}>Confirmar el mismo lote de {l.cantidad} usuarios</Button>
          </details>}
        </li>)}</ul>
      </section>
      {politica && <form onSubmit={guardar} className="space-y-3">
        <h3 className="font-semibold">Recordatorios</h3>
        <fieldset disabled={isAuditor || busy || cargando} className="grid gap-3 sm:grid-cols-2">
          <Field label="Días antes del vencimiento" required hint="0 significa el día de vencimiento. Máximo 10 valores distintos entre 0 y 30.">
            <Input value={dias} onChange={(e) => setDias(e.target.value)} />
          </Field>
          <Field label="Hora local de Lima" required><Input type="number" min={0} max={23} value={politica.hora} onChange={(e) => setPolitica({ ...politica, hora: Number(e.target.value) })} /></Field>
          <label className="flex items-center gap-2"><input type="checkbox" checked={politica.habilitado} onChange={(e) => setPolitica({ ...politica, habilitado: e.target.checked })} />Recordatorios habilitados</label>
          {!isAuditor && <Button type="submit" loading={busy}>Guardar política</Button>}
        </fieldset>
      </form>}
      <section className="space-y-3">
        <h3 className="font-semibold">Contactos suprimidos</h3>
        <p className="text-sm">No reciben nuevos intentos hasta revisar el problema o corregir su correo en el padrón.</p>
        <ul>{bloqueados.map((b) => <li key={b.email} className="flex flex-wrap items-center gap-3 py-2">
          <span>{b.email} · {b.motivo}</span>
          {!isAuditor && <Button variant="secondary" disabled={busy} onClick={() => { setEmail(b.email); setMotivo(""); }}>Revisar contacto</Button>}
        </li>)}</ul>
        {email && !isAuditor && <form onSubmit={reactivar} className="space-y-3">
          <p>Reactivar {email}</p>
          <Field label="Motivo de reactivación" required><Textarea minLength={10} maxLength={500} value={motivo} onChange={(e) => setMotivo(e.target.value)} /></Field>
          <Button type="submit" loading={busy} disabled={busy}>Reactivar con auditoría</Button>
          <Button variant="secondary" disabled={busy} onClick={() => setEmail("")}>Cancelar</Button>
        </form>}
      </section>
    </CardBody>
  </Card>;
}
