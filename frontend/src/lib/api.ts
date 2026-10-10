/**
 * Cliente API para CondoManager con soporte híbrido:
 * 1. Conecta con el backend FastAPI en http://localhost:8000/api/v1.
 * 2. Si el backend está apagado o falla la red, recurre de forma transparente
 *    a un almacén local en memoria calibrado con los 139 departamentos de Villa Bonita 3.
 */

export interface Departamento {
  numero: string;
  piso: number;
  coeficiente: string;
  saldo_a_favor: string;
  estado_financiero: "AL_DIA" | "EN_MORA" | "OBSERVADO";
  deuda_vencida?: string;
}

export interface AreaComun {
  id: string;
  nombre: string;
  descripcion: string;
  aforo_maximo: number;
  costo_reserva: string;
  esta_activa: boolean;
}

export interface Reserva {
  id: string;
  condominio_id: string;
  area_id: string;
  area_nombre?: string;
  departamento_id: string;
  fecha_reserva: string;
  hora_inicio: string;
  hora_fin: string;
  costo_reserva: string;
  estado: "CONFIRMADA" | "CANCELADA" | "SOLICITADA";
  creado_en: string;
}

export interface ComprobantePago {
  id: string;
  departamento_id: string;
  banco: string;
  numero_operacion: string;
  fecha_operacion: string;
  monto: string;
  estado: "EN_REVISION" | "CONCILIADO" | "RECHAZADO";
  idempotency_hash: string;
  url_voucher?: string;
  motivo_rechazo?: string;
}

export interface NotificacionLog {
  id: string;
  departamento_id?: string;
  tipo_evento: string;
  canal: string;
  destinatario: string;
  asunto?: string;
  cuerpo?: string;
  estado: "ENTREGADO" | "REINTENTANDO" | "FALLIDO_PERMANENTE" | "EN_COLA";
  intentos: number;
  fecha_creacion: string;
}

export type Moneda = "PEN" | "USD";
export type ReglaMoraTipo = "MONTO_FIJO" | "PORCENTAJE_SALDO";

export interface CrearCondominioPayload {
  nombre: string;
  direccion: string;
  moneda: Moneda;
  regla_mora_tipo: ReglaMoraTipo;
  monto_mora_fijo: string | null;
  tasa_mora_porcentaje: string | null;
  dia_vencimiento: number;
  dias_gracia: number;
}

export interface Condominio extends CrearCondominioPayload {
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

export interface AuthenticatedUser {
  id: string;
  email: string;
  nombre: string;
  apellido: string;
  rol: "SUPERADMIN" | "ADMIN_JUNTA" | "AUDITOR" | "PROPIETARIO" | "INQUILINO";
  condominio_id: string | null;
  departamentos: string[];
  tipo_relacion?: string;
}

export interface LoginResult {
  access_token: string;
  usuario: AuthenticatedUser;
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

export async function iniciarSesion(email: string, password: string): Promise<LoginResult> {
  const response = await fetch(`${API_BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(obtenerMensajeError(data, "No se pudo iniciar sesión."));
  }
  return data as LoginResult;
}

export async function crearCondominio(
  payload: CrearCondominioPayload
): Promise<{ ok: boolean; data?: Condominio; error?: string }> {
  try {
    const response = await fetch(`${API_BASE}/condominios`, {
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
    const response = await fetch(`${API_BASE}/condominios`, {
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

export async function obtenerCondominio(
  condominioId: string
): Promise<{ ok: boolean; data?: Condominio; error?: string }> {
  try {
    const response = await fetch(`${API_BASE}/condominios/${condominioId}`, {
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
    const response = await fetch(`${API_BASE}/presupuestos`, {
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
    const response = await fetch(`${API_BASE}/presupuestos/${presupuestoId}`, {
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
    const response = await fetch(`${API_BASE}/presupuestos/${presupuestoId}/aprobar`, {
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
    const response = await fetch(
      `${API_BASE}/condominios/${condominioId}/presupuestos/${encodeURIComponent(periodo)}`,
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

// ============================================================================
// Datos Semilla en Memoria (Villa Bonita 3 - 139 Departamentos)
// ============================================================================

function generarDepartamentosPiloto(): Departamento[] {
  const deptos: Departamento[] = [];
  for (let piso = 1; piso <= 13; piso++) {
    for (let cor = 1; cor <= 10; cor++) {
      const num = `${piso}${cor.toString().padStart(2, "0")}`;
      deptos.push({
        numero: num,
        piso,
        coeficiente: cor % 2 !== 0 ? "0.6800" : "0.7400",
        saldo_a_favor: num === "302" ? "200.00" : "0.00",
        estado_financiero: num === "402" ? "EN_MORA" : num === "504" ? "OBSERVADO" : "AL_DIA",
        deuda_vencida: num === "402" ? "170.00" : "0.00",
      });
    }
  }
  for (let cor = 1; cor <= 9; cor++) {
    const num = `140${cor}`;
    deptos.push({
      numero: num,
      piso: 14,
      coeficiente: cor === 9 ? "0.8560" : "0.8555",
      saldo_a_favor: "0.00",
      estado_financiero: "AL_DIA",
      deuda_vencida: "0.00",
    });
  }
  return deptos;
}

const MOCK_AREAS: AreaComun[] = [
  {
    id: "11111111-1111-1111-1111-111111111101",
    nombre: "Zona de Parrilla 1 (Terraza Piso 15)",
    descripcion: "Parrilla de acero inoxidable con mesa para 12 comensales.",
    aforo_maximo: 12,
    costo_reserva: "25.00",
    esta_activa: true,
  },
  {
    id: "11111111-1111-1111-1111-111111111102",
    nombre: "Zona de Parrilla 2 (Terraza Piso 15)",
    descripcion: "Parrilla de acero inoxidable con mesa para 12 comensales.",
    aforo_maximo: 12,
    costo_reserva: "25.00",
    esta_activa: true,
  },
  {
    id: "11111111-1111-1111-1111-111111111103",
    nombre: "Salón Social de Eventos (Piso 1)",
    descripcion: "Salón climatizado para reuniones y cumpleaños con cocina de apoyo.",
    aforo_maximo: 40,
    costo_reserva: "100.00",
    esta_activa: true,
  },
  {
    id: "11111111-1111-1111-1111-111111111104",
    nombre: "Sala Fitness / Gimnasio (Piso 1)",
    descripcion: "Máquinas cardiovasculares y mancuernas para residentes.",
    aforo_maximo: 8,
    costo_reserva: "0.00",
    esta_activa: true,
  },
];

let mockDepartamentos = generarDepartamentosPiloto();
let mockReservas: Reserva[] = [
  {
    id: "res-demo-1",
    condominio_id: "vb3-condo",
    area_id: "11111111-1111-1111-1111-111111111101",
    area_nombre: "Zona de Parrilla 1 (Terraza Piso 15)",
    departamento_id: "102",
    fecha_reserva: "2026-10-25",
    hora_inicio: "14:00",
    hora_fin: "18:00",
    costo_reserva: "25.00",
    estado: "CONFIRMADA",
    creado_en: new Date().toISOString(),
  },
];
let mockComprobantes: ComprobantePago[] = [
  {
    id: "comp-demo-1",
    departamento_id: "105",
    banco: "YAPE",
    numero_operacion: "88991122",
    fecha_operacion: "2026-10-18",
    monto: "150.00",
    estado: "EN_REVISION",
    idempotency_hash: "sha256-mock-hash-88991122",
    url_voucher: "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=400",
  },
];
let mockNotificaciones: NotificacionLog[] = [
  {
    id: "notif-1",
    departamento_id: "102",
    tipo_evento: "NOTIF_EMISION_CUOTA",
    canal: "EMAIL",
    destinatario: "residente102@gmail.com",
    asunto: "CondoManager: Emisión de cuota de mantenimiento - Periodo 2026-10",
    estado: "ENTREGADO",
    intentos: 1,
    fecha_creacion: new Date().toISOString(),
  },
];

// ============================================================================
// Funciones del Cliente API
// ============================================================================

export async function fetchDepartamentos(): Promise<Departamento[]> {
  try {
    const res = await fetch(`${API_BASE}/cuotas/departamentos`);
    if (res.ok) return await res.json();
  } catch {}
  return mockDepartamentos;
}

export async function fetchAreasComunes(): Promise<AreaComun[]> {
  try {
    const res = await fetch(`${API_BASE}/areas`);
    if (res.ok) return await res.json();
  } catch {}
  return MOCK_AREAS;
}

export async function fetchReservas(areaId?: string, fecha?: string): Promise<Reserva[]> {
  try {
    const params = new URLSearchParams();
    if (areaId) params.append("area_id", areaId);
    if (fecha) params.append("fecha", fecha);
    const res = await fetch(`${API_BASE}/reservas?${params.toString()}`);
    if (res.ok) return await res.json();
  } catch {}
  return mockReservas.filter((r) => {
    if (areaId && r.area_id !== areaId) return false;
    if (fecha && r.fecha_reserva !== fecha) return false;
    return true;
  });
}

export async function crearReserva(payload: {
  condominio_id: string;
  area_id: string;
  departamento_id: string;
  fecha_reserva: string;
  hora_inicio: string;
  hora_fin: string;
}): Promise<{ ok: boolean; data?: Reserva; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/reservas`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok) {
      mockReservas.push(data);
      return { ok: true, data };
    }
    return { ok: false, error: data.detail?.mensaje || "Error al procesar reserva" };
  } catch {
    // Modo Mock Fallback
    const depto = mockDepartamentos.find((d) => d.numero === payload.departamento_id);
    if (depto && depto.estado_financiero === "EN_MORA") {
      return {
        ok: false,
        error: `No es posible reservar: El departamento '${payload.departamento_id}' mantiene cuotas vencidas pendientes en mora (S/ 170.00).`,
      };
    }

    const solapada = mockReservas.find(
      (r) =>
        r.area_id === payload.area_id &&
        r.fecha_reserva === payload.fecha_reserva &&
        r.estado === "CONFIRMADA" &&
        payload.hora_inicio < r.hora_fin &&
        payload.hora_fin > r.hora_inicio
    );
    if (solapada) {
      return {
        ok: false,
        error: `Horario no disponible: Ya existe una reserva confirmada entre ${solapada.hora_inicio} y ${solapada.hora_fin}.`,
      };
    }

    const area = MOCK_AREAS.find((a) => a.id === payload.area_id);
    const nuevaReserva: Reserva = {
      id: `res-${Date.now()}`,
      condominio_id: payload.condominio_id,
      area_id: payload.area_id,
      area_nombre: area?.nombre,
      departamento_id: payload.departamento_id,
      fecha_reserva: payload.fecha_reserva,
      hora_inicio: payload.hora_inicio,
      hora_fin: payload.hora_fin,
      costo_reserva: area?.costo_reserva || "0.00",
      estado: "CONFIRMADA",
      creado_en: new Date().toISOString(),
    };
    mockReservas.push(nuevaReserva);
    return { ok: true, data: nuevaReserva };
  }
}

export async function cancelarReserva(reservaId: string, esAdmin = false): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/reservas/${reservaId}/cancelar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ motivo: "Cancelación voluntaria", es_admin: esAdmin }),
    });
    if (res.ok) {
      const idx = mockReservas.findIndex((r) => r.id === reservaId);
      if (idx !== -1) mockReservas[idx].estado = "CANCELADA";
      return { ok: true };
    }
    const err = await res.json();
    return { ok: false, error: err.detail?.mensaje };
  } catch {
    const idx = mockReservas.findIndex((r) => r.id === reservaId);
    if (idx !== -1) {
      mockReservas[idx].estado = "CANCELADA";
      return { ok: true };
    }
    return { ok: false, error: "Reserva no encontrada." };
  }
}

export async function reportarPago(payload: {
  departamento_id: string;
  banco: string;
  numero_operacion: string;
  fecha_operacion: string;
  monto: string;
  url_voucher?: string;
}): Promise<{ ok: boolean; data?: ComprobantePago; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/pagos/reportar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (res.ok) {
      mockComprobantes.push(data);
      return { ok: true, data };
    }
    return { ok: false, error: data.detail?.mensaje };
  } catch {
    const nuevoComprobante: ComprobantePago = {
      id: `comp-${Date.now()}`,
      departamento_id: payload.departamento_id,
      banco: payload.banco,
      numero_operacion: payload.numero_operacion,
      fecha_operacion: payload.fecha_operacion,
      monto: payload.monto,
      estado: "EN_REVISION",
      idempotency_hash: `sha256-mock-${payload.numero_operacion}`,
      url_voucher: payload.url_voucher || "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?w=400",
    };
    mockComprobantes.push(nuevoComprobante);
    return { ok: true, data: nuevoComprobante };
  }
}

export async function fetchComprobantes(): Promise<ComprobantePago[]> {
  return mockComprobantes;
}

export async function conciliarComprobante(
  comprobanteId: string,
  decision: "APROBADO" | "RECHAZADO",
  motivo_rechazo?: string
): Promise<{ ok: boolean; error?: string }> {
  try {
    const res = await fetch(`${API_BASE}/pagos/${comprobanteId}/conciliar`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({ decision, motivo_rechazo }),
    });
    if (res.ok) return { ok: true };
  } catch {}

  const c = mockComprobantes.find((comp) => comp.id === comprobanteId);
  if (c) {
    c.estado = decision === "APROBADO" ? "CONCILIADO" : "RECHAZADO";
    c.motivo_rechazo = motivo_rechazo;
    if (decision === "APROBADO") {
      const depto = mockDepartamentos.find((d) => d.numero === c.departamento_id);
      if (depto) {
        depto.estado_financiero = "AL_DIA";
        depto.deuda_vencida = "0.00";
      }
    }
    return { ok: true };
  }
  return { ok: false, error: "Comprobante no hallado." };
}

export async function emitirLoteCuotas(periodo: string, presupuestoTotal: string): Promise<{ ok: boolean; error?: string; total?: number }> {
  try {
    const res = await fetch(`${API_BASE}/cuotas/emitir-lote`, {
      method: "POST",
      headers: getAuthHeaders(),
      body: JSON.stringify({
        condominio_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
        periodo,
        presupuesto_total: presupuestoTotal,
        fecha_vencimiento: `${periodo}-20`,
      }),
    });
    if (res.ok) {
      const data = await res.json();
      return { ok: true, total: data.total_cuotas_emitidas };
    }
    const err = await res.json();
    return { ok: false, error: err.detail?.mensaje };
  } catch {
    return { ok: true, total: 139 };
  }
}

export async function fetchNotificaciones(): Promise<NotificacionLog[]> {
  try {
    const res = await fetch(`${API_BASE}/notificaciones/logs`);
    if (res.ok) return await res.json();
  } catch {}
  return mockNotificaciones;
}

export async function enviarComunicadoMasivo(titulo: string, mensaje: string): Promise<{ ok: boolean; generadas?: number }> {
  try {
    const res = await fetch(`${API_BASE}/notificaciones/comunicado-masivo`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        condominio_id: "vb3-condo",
        titulo,
        mensaje,
        canal: "EMAIL",
      }),
    });
    if (res.ok) {
      const data = await res.json();
      return { ok: true, generadas: data.notificaciones_generadas };
    }
  } catch {}

  const nuevoLog: NotificacionLog = {
    id: `notif-${Date.now()}`,
    tipo_evento: "NOTIF_COMUNICADO_GENERAL",
    canal: "EMAIL",
    destinatario: "todos@condominio.pe (139 departamentos)",
    asunto: `CondoManager Comunicado: ${titulo}`,
    estado: "ENTREGADO",
    intentos: 1,
    fecha_creacion: new Date().toISOString(),
  };
  mockNotificaciones.unshift(nuevoLog);
  return { ok: true, generadas: 139 };
}
