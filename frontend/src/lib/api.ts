/** Cliente autenticado: los fallos de red o autorización nunca generan éxitos simulados. */
import type { SessionUser, TipoRelacion } from "./session";

export interface Departamento {
  id: string;
  condominio_id?: string;
  edificio_id?: string;
  edificio_nombre?: string;
  activo?: boolean;
  numero: string;
  piso: number;
  coeficiente: string;
  saldo_a_favor: string;
  estado_financiero: "AL_DIA" | "EN_MORA" | "OBSERVADO";
  deuda_vencida?: string;
}

export interface Edificio {
  id: string;
  condominio_id: string;
  nombre_bloque: string;
  total_pisos: number;
}

export interface DepartamentoRegistrado {
  id: string;
  edificio_id: string;
  numero: string;
  piso: number;
  coeficiente_participacion: string;
  saldo_a_favor: string;
  estado_financiero: "AL_DIA" | "EN_MORA" | "OBSERVADO";
  activo: boolean;
}

export interface FilaImportacion {
  fila: number;
  numero: string;
  piso: number | null;
  edificio: string;
  coeficiente: string;
  total_pisos: number | null;
  estado: "NUEVA" | "CREADA" | "YA_EXISTENTE" | "ERROR";
  errores: string[];
}

export interface ResultadoImportacion {
  total_filas: number;
  nuevas: number;
  creadas: number;
  ya_existentes: number;
  rechazadas: number;
  filas: FilaImportacion[];
}

/** Adaptador para las vistas de cuotas que usan el nombre histórico coeficiente. */
export function departamentoParaPortal(departamento: DepartamentoRegistrado): Departamento {
  return { ...departamento, coeficiente: departamento.coeficiente_participacion };
}

export interface AreaComun {
  id: string;
  condominio_id: string;
  nombre: string;
  descripcion: string | null;
  aforo_maximo: number;
  costo_reserva: string;
  esta_activa: boolean;
  edificio_id: string | null;
  edificio_nombre: string | null;
  hora_apertura: string;
  hora_cierre: string;
  tiempo_maximo_horas: number;
  moneda: Moneda;
  zona_horaria: "America/Lima";
}

export interface ConfigurarAreaPayload {
  nombre: string;
  descripcion: string | null;
  edificio_id: string | null;
  aforo_maximo: number;
  costo_reserva: string;
  hora_apertura: string;
  hora_cierre: string;
  tiempo_maximo_horas: number;
}

function rutaAreas(condominioId: string): string {
  return `/condominios/${encodeURIComponent(condominioId)}/areas`;
}

export function listarCatalogoAreas(condominioId: string, activa?: boolean, limit = 50, offset = 0): Promise<AreaComun[]> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (activa !== undefined) params.set("esta_activa", String(activa));
  return recursoRequest(`${rutaAreas(condominioId)}?${params}`);
}

export function registrarArea(condominioId: string, datos: ConfigurarAreaPayload): Promise<AreaComun> {
  return recursoRequest(rutaAreas(condominioId), { method: "POST", body: JSON.stringify(datos) });
}

export function configurarArea(condominioId: string, areaId: string, datos: ConfigurarAreaPayload): Promise<AreaComun> {
  return recursoRequest(`${rutaAreas(condominioId)}/${encodeURIComponent(areaId)}`, { method: "PUT", body: JSON.stringify(datos) });
}

export function cambiarEstadoArea(condominioId: string, areaId: string, esta_activa: boolean): Promise<AreaComun> {
  return recursoRequest(`${rutaAreas(condominioId)}/${encodeURIComponent(areaId)}/estado`, { method: "PATCH", body: JSON.stringify({ esta_activa }) });
}

export interface Reserva {
  id: string;
  condominio_id: string;
  area_id: string;
  area_nombre?: string | null;
  departamento_id: string;
  fecha_reserva: string;
  hora_inicio: string;
  hora_fin: string;
  costo_reserva: string;
  moneda: Moneda;
  zona_horaria: "America/Lima" | "UTC";
  estado: "CONFIRMADA" | "CANCELADA" | "SOLICITADA" | "RECHAZADA" | "COMPLETADA";
  creado_en: string;
}

export interface ComprobantePago {
  id: string;
  departamento_id: string;
  banco: string;
  numero_operacion: string;
  fecha_operacion: string;
  monto: string;
  estado: "EN_REVISION" | "APROBADO" | "RECHAZADO" | "OBSERVADO";
  idempotency_hash: string;
  url_voucher: string;
  motivo_rechazo: string | null;
}

export interface NotificacionLog {
  id: string;
  condominio_id: string;
  departamento_id: string | null;
  usuario_destinatario_id: string | null;
  evento_id: string | null;
  tipo_evento: string;
  canal: "EMAIL" | "WHATSAPP" | "SMS" | "PUSH";
  destinatario: string;
  asunto: string | null;
  cuerpo: string;
  estado: "ENTREGADO" | "ENVIADO" | "REINTENTANDO" | "FALLIDO_PERMANENTE" | "EN_COLA";
  intentos: number;
  ciclo: number;
  transporte: "SIMULADO" | "PROVEEDOR";
  proximo_reintento: string | null;
  error_mensaje: string | null;
  proveedor_message_id: string | null;
  fecha_creacion: string;
  fecha_actualizacion: string;
}

export type Moneda = "PEN" | "USD";
export type ReglaMoraTipo = "MONTO_DIARIO" | "MONTO_FIJO" | "PORCENTAJE_SALDO";

export interface CrearCondominioPayload {
  nombre: string;
  direccion: string;
  moneda: Moneda;
  regla_mora_tipo: ReglaMoraTipo;
  monto_mora_fijo: string | null;
  monto_mora_diario?: string | null;
  tasa_mora_porcentaje: string | null;
  dia_vencimiento: number;
  dias_gracia: number;
}

export interface Condominio extends CrearCondominioPayload {
  politica_version: number;
  id: string;
  activo: boolean;
  creado_en: string;
}

export type EstadoPresupuesto = "BORRADOR" | "APROBADO";

export interface DatosPresupuestoPayload {
  periodo: string;
  moneda: Moneda;
  monto_total: string;
  fecha_vencimiento: string;
}

export interface CrearPresupuestoPayload extends DatosPresupuestoPayload {
  condominio_id: string;
}

export interface PresupuestoMensual extends CrearPresupuestoPayload {
  id: string;
  estado: EstadoPresupuesto;
  creado_por: string;
  creado_en: string;
  aprobado_por: string | null;
  aprobado_en: string | null;
  actualizado_en: string;
}

export interface PresupuestoApiResult {
  ok: boolean;
  data?: PresupuestoMensual;
  error?: string;
  errorCode?: string;
  notFound?: boolean;
}

export type AuthenticatedUser = SessionUser;

export interface LoginResult {
  access_token: string;
  usuario: AuthenticatedUser;
}

export interface CuentaUsuario {
  id: string;
  email: string;
  nombre: string;
  apellido: string;
  telefono: string | null;
  documento_identidad: string;
  esta_activo: boolean;
  creado_en: string;
}

export interface CrearUsuarioPayload {
  email: string;
  password: string;
  nombre: string;
  apellido: string;
  telefono: string | null;
  documento_identidad: string;
}

export type RolContextual = "ADMIN_JUNTA" | "AUDITOR" | "RESIDENTE";

export interface AsignacionRol {
  usuario_id: string;
  condominio_id: string;
  rol: RolContextual | "SUPERADMIN";
  es_activo: boolean;
}

export interface CuentaUsuarioConRol extends CuentaUsuario {
  rol: AsignacionRol["rol"];
  rol_activo: boolean;
  es_superadmin: boolean;
}

export interface VinculoUsuario {
  id: string;
  usuario_id: string;
  condominio_id: string;
  departamento_id: string;
  numero: string;
  edificio_id: string;
  edificio_nombre: string;
  tipo_relacion: TipoRelacion;
  es_activo: boolean;
  departamento_activo: boolean;
}

function rutaVinculos(condominioId: string, usuarioId: string): string {
  return `/condominios/${encodeURIComponent(condominioId)}/usuarios/${encodeURIComponent(usuarioId)}/departamentos`;
}

export function listarVinculosUsuario(condominioId: string, usuarioId: string): Promise<VinculoUsuario[]> {
  return recursoRequest(rutaVinculos(condominioId, usuarioId));
}

export function asignarVinculoUsuario(condominioId: string, usuarioId: string, departamentoId: string, tipo_relacion: TipoRelacion): Promise<VinculoUsuario> {
  return recursoRequest(`${rutaVinculos(condominioId, usuarioId)}/${encodeURIComponent(departamentoId)}`, {
    method: "PUT", body: JSON.stringify({ tipo_relacion }),
  });
}

export function revocarVinculoUsuario(condominioId: string, usuarioId: string, departamentoId: string): Promise<VinculoUsuario> {
  return recursoRequest(`${rutaVinculos(condominioId, usuarioId)}/${encodeURIComponent(departamentoId)}`, { method: "DELETE" });
}

function rutaRol(condominioId: string, usuarioId: string): string {
  return `/condominios/${encodeURIComponent(condominioId)}/usuarios/${encodeURIComponent(usuarioId)}/rol`;
}

export function consultarRolUsuario(condominioId: string, usuarioId: string): Promise<AsignacionRol> {
  return recursoRequest(rutaRol(condominioId, usuarioId));
}

export function asignarRolUsuario(condominioId: string, usuarioId: string, rol: RolContextual): Promise<AsignacionRol> {
  return recursoRequest(rutaRol(condominioId, usuarioId), { method: "PUT", body: JSON.stringify({ rol }) });
}

export function revocarRolUsuario(condominioId: string, usuarioId: string): Promise<AsignacionRol> {
  return recursoRequest(rutaRol(condominioId, usuarioId), { method: "DELETE" });
}

export function listarUsuarios(condominioId: string, limit = 50, offset = 0): Promise<CuentaUsuarioConRol[]> {
  return recursoRequest(`/condominios/${encodeURIComponent(condominioId)}/usuarios?limit=${limit}&offset=${offset}`);
}

export function crearUsuario(condominioId: string, datos: CrearUsuarioPayload): Promise<CuentaUsuario> {
  return recursoRequest(`/condominios/${encodeURIComponent(condominioId)}/usuarios`, {
    method: "POST", body: JSON.stringify(datos),
  });
}

export function cambiarEstadoUsuario(condominioId: string, usuarioId: string, esta_activo: boolean): Promise<CuentaUsuario> {
  return recursoRequest(`/usuarios/${encodeURIComponent(usuarioId)}/estado?condominio_id=${encodeURIComponent(condominioId)}`, {
    method: "PATCH", body: JSON.stringify({ esta_activo }),
  });
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("condo_token");
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
  }
  return headers;
}

function obtenerMensajeError(data: unknown, fallback: string): string {
  if (!data || typeof data !== "object") return fallback;
  const payload = data as {
    mensaje?: string;
    detail?: { mensaje?: string } | string;
  };
  if (payload.mensaje) return payload.mensaje;
  if (typeof payload.detail === "string") return payload.detail;
  return payload.detail?.mensaje || fallback;
}

function obtenerCodigoError(data: unknown): string | undefined {
  if (!data || typeof data !== "object") return undefined;
  const payload = data as {
    error_code?: string;
    detail?: { error_code?: string };
  };
  return payload.error_code || payload.detail?.error_code;
}

export async function iniciarSesion(email: string, password: string, condominioId?: string): Promise<LoginResult> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password, condominio_id: condominioId }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw data;
  }
  return data as LoginResult;
}

export function obtenerSesion(): Promise<AuthenticatedUser> {
  return recursoRequest("/auth/me");
}

async function fetchProtegido(ruta: string, init: RequestInit): Promise<Response> {
  const response = await fetch(`${API_BASE}${ruta}`, init);
  if (response.status === 401 && typeof window !== "undefined" && typeof window.dispatchEvent === "function") {
    window.dispatchEvent(new Event("condomanager:sesion-revocada"));
  }
  return response;
}

async function recursoRequest<T>(ruta: string, init: RequestInit = {}): Promise<T> {
  const response = await fetchProtegido(ruta, { ...init, headers: getAuthHeaders() });
  const data = await response.json();
  if (!response.ok) {
    const payload = data.detail && typeof data.detail === "object" ? data.detail : data;
    throw new ApiError(obtenerMensajeError(data, "No se pudo completar la operación."),
      response.status, obtenerCodigoError(data), payload.detalles);
  }
  return data as T;
}

export class ApiError extends Error {
  constructor(message: string, public status: number, public errorCode?: string,
    public detalles?: Record<string, unknown>) {
    super(message);
  }
}

function contextoQuery(condominioId?: string | null): string {
  return condominioId ? `?condominio_id=${encodeURIComponent(condominioId)}` : "";
}

async function estructuraRequest<T>(condominioId: string, ruta: string, init: RequestInit = {}): Promise<T> {
  const headers = getAuthHeaders();
  if (init.body instanceof FormData) delete headers["Content-Type"];
  let response: Response;
  try {
    response = await fetchProtegido(`/condominios/${encodeURIComponent(condominioId)}${ruta}`, {
      ...init, headers,
    });
  } catch {
    throw new Error("No se pudo conectar con la API. Comprueba la conexión e inténtalo de nuevo.");
  }
  const data = await response.json();
  if (!response.ok) throw new Error(obtenerMensajeError(data, "No se pudo completar la operación de estructura."));
  return data as T;
}

export function listarEdificios(condominioId: string): Promise<Edificio[]> {
  return estructuraRequest(condominioId, "/edificios");
}

export function registrarEdificio(condominioId: string, nombre_bloque: string, total_pisos: number): Promise<Edificio> {
  return estructuraRequest(condominioId, "/edificios", {
    method: "POST", body: JSON.stringify({ nombre_bloque, total_pisos }),
  });
}

export function listarDepartamentos(condominioId: string): Promise<DepartamentoRegistrado[]> {
  return estructuraRequest(condominioId, "/departamentos");
}

export function registrarDepartamento(condominioId: string, edificioId: string, datos: {
  numero: string; piso: number; coeficiente_participacion: string;
}): Promise<DepartamentoRegistrado> {
  return estructuraRequest(condominioId, `/edificios/${encodeURIComponent(edificioId)}/departamentos`, {
    method: "POST", body: JSON.stringify(datos),
  });
}

export function cambiarEstadoDepartamento(condominioId: string, departamentoId: string, activo: boolean): Promise<DepartamentoRegistrado> {
  return estructuraRequest(condominioId, `/departamentos/${encodeURIComponent(departamentoId)}/estado`, {
    method: "PATCH", body: JSON.stringify({ activo }),
  });
}

export function importarEstructura(condominioId: string, archivo: File, confirmar = false): Promise<ResultadoImportacion> {
  const body = new FormData();
  body.append("archivo", archivo);
  return estructuraRequest(condominioId, `/importaciones/${confirmar ? "confirmar" : "previsualizar"}`, {
    method: "POST", body,
  });
}

export async function crearCondominio(
  payload: CrearCondominioPayload
): Promise<{ ok: boolean; data?: Condominio; error?: string }> {
  try {
    const response = await fetchProtegido(`/condominios`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        ok: false,
        error: obtenerMensajeError(data, "No se pudo guardar el condominio."),
      };
    }
    return { ok: true, data: data as Condominio };
  } catch {
    return {
      ok: false,
      error: "No se pudo conectar con la API. La configuración no fue guardada.",
    };
  }
}

export async function listarCondominios(): Promise<{
  ok: boolean;
  data?: Condominio[];
  error?: string;
}> {
  try {
    const response = await fetchProtegido(`/condominios`, {
      headers: getAuthHeaders(),
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        ok: false,
        error: obtenerMensajeError(data, "No se pudieron consultar los condominios."),
      };
    }
    return { ok: true, data: data as Condominio[] };
  } catch {
    return { ok: false, error: "No se pudo conectar con la API." };
  }
}

export async function actualizarPoliticaMora(condominio: Condominio, datos: CrearCondominioPayload, motivo: string): Promise<{ ok: boolean; data?: Condominio; error?: string }> {
  try {
    const { nombre: _nombre, direccion: _direccion, moneda: _moneda, ...politica } = datos;
    const response = await fetchProtegido(`/condominios/${encodeURIComponent(condominio.id)}/politica-mora`, {
      method: "PUT", headers: getAuthHeaders(),
      body: JSON.stringify({ ...politica, version_esperada: condominio.politica_version, motivo }),
    });
    const data = await response.json();
    return response.ok ? { ok: true, data } : { ok: false, error: obtenerMensajeError(data, "No se pudo actualizar la política. Recargue si cambió la versión.") };
  } catch {
    return { ok: false, error: "No se pudo conectar con la API. Recargue antes de reintentar." };
  }
}

export async function obtenerCondominio(
  condominioId: string
): Promise<{ ok: boolean; data?: Condominio; error?: string }> {
  try {
    const response = await fetchProtegido(`/condominios/${condominioId}`, {
      headers: getAuthHeaders(),
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        ok: false,
        error: obtenerMensajeError(data, "No se pudo consultar el condominio."),
      };
    }
    return { ok: true, data: data as Condominio };
  } catch {
    return { ok: false, error: "No se pudo conectar con la API." };
  }
}

export async function crearPresupuesto(
  payload: CrearPresupuestoPayload
): Promise<PresupuestoApiResult> {
  try {
    const response = await fetchProtegido(`/presupuestos`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        ok: false,
        error: obtenerMensajeError(data, "No se pudo guardar el presupuesto."),
        errorCode: obtenerCodigoError(data),
      };
    }
    return { ok: true, data: data as PresupuestoMensual };
  } catch {
    return {
      ok: false,
      error: "No se pudo conectar con la API. El presupuesto no fue guardado.",
    };
  }
}

export async function actualizarPresupuesto(
  presupuestoId: string,
  payload: DatosPresupuestoPayload
): Promise<PresupuestoApiResult> {
  try {
    const response = await fetchProtegido(`/presupuestos/${presupuestoId}`, {
      method: "PUT",
      headers: getAuthHeaders(),
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        ok: false,
        error: obtenerMensajeError(data, "No se pudo actualizar el presupuesto."),
        errorCode: obtenerCodigoError(data),
      };
    }
    return { ok: true, data: data as PresupuestoMensual };
  } catch {
    return {
      ok: false,
      error: "No se pudo conectar con la API. El presupuesto no fue actualizado.",
    };
  }
}

export async function aprobarPresupuesto(
  presupuestoId: string
): Promise<PresupuestoApiResult> {
  try {
    const response = await fetchProtegido(`/presupuestos/${presupuestoId}/aprobar`, {
      method: "POST",
      headers: getAuthHeaders(),
    });
    const data = await response.json();
    if (!response.ok) {
      return {
        ok: false,
        error: obtenerMensajeError(data, "No se pudo aprobar el presupuesto."),
        errorCode: obtenerCodigoError(data),
      };
    }
    return { ok: true, data: data as PresupuestoMensual };
  } catch {
    return {
      ok: false,
      error: "No se pudo conectar con la API. El presupuesto no fue aprobado.",
    };
  }
}

export async function obtenerPresupuestoPorPeriodo(
  condominioId: string,
  periodo: string
): Promise<PresupuestoApiResult> {
  try {
    const response = await fetchProtegido(
      `/condominios/${condominioId}/presupuestos/${encodeURIComponent(periodo)}`,
      { headers: getAuthHeaders() }
    );
    const data = await response.json();
    const errorCode = obtenerCodigoError(data);
    if (response.status === 404 && errorCode === "PRESUPUESTO_NO_ENCONTRADO") {
      return { ok: true, notFound: true };
    }
    if (!response.ok) {
      return {
        ok: false,
        error: obtenerMensajeError(data, "No se pudo consultar el presupuesto."),
        errorCode,
      };
    }
    return { ok: true, data: data as PresupuestoMensual };
  } catch {
    return { ok: false, error: "No se pudo conectar con la API." };
  }
}

export function fetchDepartamentos(condominioId?: string | null): Promise<Departamento[]> {
  return recursoRequest(`/cuotas/departamentos${contextoQuery(condominioId)}`);
}

export function fetchAreasComunes(condominioId?: string | null): Promise<AreaComun[]> {
  return recursoRequest(`/areas${contextoQuery(condominioId)}`);
}

export interface HorarioOcupado { hora_inicio: string; hora_fin: string }

export function fetchDisponibilidad(areaId: string, fecha: string): Promise<HorarioOcupado[]> {
  return recursoRequest(`/areas/${encodeURIComponent(areaId)}/disponibilidad?fecha=${encodeURIComponent(fecha)}`, { cache: "no-store" });
}

export function fetchReservas(areaId?: string, fecha?: string, condominioId?: string | null): Promise<Reserva[]> {
  const params = new URLSearchParams();
  if (areaId) params.set("area_id", areaId);
  if (fecha) params.set("fecha", fecha);
  if (condominioId) params.set("condominio_id", condominioId);
  return recursoRequest(`/reservas?${params}`);
}

export async function crearReserva(payload: {
  condominio_id: string;
  area_id: string;
  departamento_id: string;
  fecha_reserva: string;
  hora_inicio: string;
  hora_fin: string;
}): Promise<{ ok: boolean; data?: Reserva; error?: string; errorCode?: string }> {
  try {
    const data = await recursoRequest<Reserva>("/reservas", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    return { ok: true, data };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "No se pudo crear la reserva.",
      errorCode: error instanceof ApiError ? error.errorCode : undefined };
  }
}

export interface ReservaCancelada {
  id: string;
  estado: "CANCELADA";
  mensaje: string;
  fecha_cancelacion: string;
  ajuste_economico: {
    estado: "NO_APLICA" | "PENDIENTE" | "APLICADO";
    monto: string;
    referencia: string | null;
  };
}

export async function cancelarReserva(
  reservaId: string,
  motivo = "Cancelación voluntaria",
): Promise<{ ok: boolean; data?: ReservaCancelada; error?: string }> {
  try {
    const data = await recursoRequest<ReservaCancelada>(`/reservas/${encodeURIComponent(reservaId)}/cancelar`, {
      method: "POST",
      body: JSON.stringify({ motivo }),
    });
    return { ok: true, data };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "No se pudo cancelar." };
  }
}

export async function reportarPago(payload: {
  departamento_id: string;
  banco: string;
  numero_operacion: string;
  fecha_operacion: string;
  monto: string;
  archivo_voucher: File;
}): Promise<{ ok: boolean; error?: string; errorCode?: string; duplicado?: boolean }> {
  try {
    const form = new FormData();
    for (const [campo, valor] of Object.entries(payload)) form.append(campo, valor);
    const headers = getAuthHeaders();
    delete headers["Content-Type"];
    const response = await fetchProtegido("/pagos/reportar", {
      method: "POST",
      headers,
      body: form,
    });
    const data = await response.json();
    const errorCode = obtenerCodigoError(data);
    if (!response.ok) return { ok: false, error: obtenerMensajeError(data, "No se pudo reportar el pago."), errorCode };
    return { ok: true, duplicado: data.codigo === "VOUCHER_EN_EVALUACION" };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "No se pudo reportar el pago." };
  }
}

export async function subsanarVoucher(comprobanteId: string, archivo: File): Promise<void> {
  const form = new FormData();
  form.append("archivo_voucher", archivo);
  const headers = getAuthHeaders();
  delete headers["Content-Type"];
  const response = await fetchProtegido(`/pagos/${encodeURIComponent(comprobanteId)}/voucher`, { method: "PUT", headers, body: form });
  const data = await response.json();
  if (!response.ok) throw new Error(obtenerMensajeError(data, "No se pudo subir el voucher."));
}

export interface EvidenciaVoucher {
  evidencia_id: string;
  content_type: string;
  creado_en: string;
}

export async function listarEvidencias(comprobanteId: string, signal?: AbortSignal): Promise<EvidenciaVoucher[]> {
  const response = await fetchProtegido(`/pagos/${encodeURIComponent(comprobanteId)}/evidencias`, {
    headers: getAuthHeaders(), signal,
  });
  if (!response.ok) throw new Error("No se pudo consultar el historial de evidencia.");
  return response.json();
}

export async function visualizarVoucher(comprobanteId: string, evidenciaId: string, signal?: AbortSignal): Promise<Blob> {
  const query = new URLSearchParams({ disposicion: "inline" });
  if (evidenciaId) query.set("evidencia_id", evidenciaId);
  const response = await fetchProtegido(`/pagos/${encodeURIComponent(comprobanteId)}/voucher?${query}`, {
    headers: getAuthHeaders(), signal,
  });
  if (!response.ok) throw new Error("No se pudo visualizar la evidencia. Verifique su sesión y permisos.");
  const blob = await response.blob();
  if (!["image/png", "image/jpeg", "application/pdf"].includes(blob.type)) throw new Error("Formato de evidencia no admitido.");
  return blob;
}

export async function descargarVoucher(comprobante: ComprobantePago): Promise<void> {
  const response = await fetchProtegido(`/pagos/${encodeURIComponent(comprobante.id)}/voucher`, {
    headers: getAuthHeaders(),
  });
  if (!response.ok) {
    const data = await response.json();
    throw new Error(obtenerMensajeError(data, "No se pudo recuperar el voucher."));
  }
  const url = URL.createObjectURL(await response.blob());
  const enlace = document.createElement("a");
  enlace.href = url;
  const extension = { "image/png": "png", "image/jpeg": "jpg", "application/pdf": "pdf" }[response.headers.get("Content-Type") || ""];
  enlace.download = `voucher-${comprobante.id}${extension ? `.${extension}` : ""}`;
  document.body.appendChild(enlace);
  enlace.click();
  enlace.remove();
  // URL exclusiva de descarga; nunca se envía al servidor ni se persiste.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export interface Solvencia {
  departamento_id: string;
  saldo_vencido: string;
  habilitado_reservas: boolean;
}

export function fetchSolvencia(departamentoId: string): Promise<Solvencia> {
  return recursoRequest(`/pagos/solvencia/${encodeURIComponent(departamentoId)}`);
}

export function fetchComprobantes(condominioId?: string | null): Promise<ComprobantePago[]> {
  return recursoRequest(`/pagos/comprobantes${contextoQuery(condominioId)}`);
}

export async function conciliarComprobante(
  comprobanteId: string,
  decision: "APROBADO" | "RECHAZADO" | "OBSERVADO",
  motivo_rechazo?: string
): Promise<{ ok: boolean; error?: string }> {
  try {
    await recursoRequest(`/pagos/${encodeURIComponent(comprobanteId)}/conciliar`, {
      method: "POST",
      body: JSON.stringify({ decision, motivo_rechazo }),
    });
    return { ok: true };
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : "No se pudo conciliar." };
  }
}

export async function emitirLoteCuotas(periodo: string, condominioId: string): Promise<{ ok: boolean; error?: string; total?: number }> {
  try {
    const res = await fetchProtegido(`/cuotas/emitir-lote`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        condominio_id: condominioId,
        periodo,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      return { ok: true, total: data.total_cuotas_emitidas };
    }
    const err = await res.json();
    return { ok: false, error: obtenerMensajeError(err, "No se pudo emitir el lote.") };
  } catch {
    return { ok: false, error: "No se pudo conectar con la API para emitir el lote." };
  }
}

export function fetchNotificaciones(condominioId?: string | null): Promise<NotificacionLog[]> {
  return recursoRequest(`/notificaciones/logs${contextoQuery(condominioId)}`);
}

export type TipoAlertaNotificacion =
  | "ERROR_DEFINITIVO" | "INTENTOS_AGOTADOS" | "ACEPTACION_INCIERTA"
  | "DESTINATARIO_INVALIDO" | "PROVEEDOR_NO_CONFIGURADO";

export interface AlertaNotificacion {
  id: string;
  notificacion_id: string;
  condominio_id: string;
  departamento_id: string;
  departamento_numero: string;
  tipo_evento: string;
  ciclo: number;
  tipo: TipoAlertaNotificacion;
  mensaje: string;
  estado: "ABIERTA" | "ATENDIDA";
  creada_en: string;
  atendida_en: string | null;
  atendida_por: string | null;
}

export function listarAlertasNotificacion(condominioId?: string | null): Promise<AlertaNotificacion[]> {
  return recursoRequest(`/notificaciones/alertas${contextoQuery(condominioId)}`);
}

export function atenderAlertaNotificacion(id: string): Promise<AlertaNotificacion> {
  return recursoRequest(`/notificaciones/alertas/${encodeURIComponent(id)}/atender`, { method: "POST" });
}

export function reenviarNotificacion(id: string, nuevo_destinatario: string): Promise<NotificacionLog> {
  return recursoRequest(`/notificaciones/reenviar/${encodeURIComponent(id)}`, {
    method: "POST", body: JSON.stringify({ nuevo_destinatario }),
  });
}

export async function enviarComunicadoMasivo(titulo: string, mensaje: string, condominioId: string): Promise<{ ok: boolean; generadas?: number }> {
  try {
    const data = await recursoRequest<{ generadas: number }>("/notificaciones/comunicado-masivo", {
      method: "POST",
      body: JSON.stringify({
        condominio_id: condominioId,
        titulo,
        mensaje,
        canal: "EMAIL",
      }),
    });
    return { ok: true, generadas: data.generadas };
  } catch {
    return { ok: false };
  }
}
