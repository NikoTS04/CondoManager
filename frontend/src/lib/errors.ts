/**
 * Diccionario único de mensajes para los `error_code` del backend (DESIGN.md §5 y §10).
 * Formato: qué pasó + qué hacer. El código original se muestra como detalle secundario.
 */

const MENSAJES: Record<string, string> = {
  NO_AUTENTICADO: "Tu sesión no está iniciada. Ingresa nuevamente para continuar.",
  TOKEN_EXPIRADO: "Tu sesión expiró. Ingresa nuevamente para continuar.",
  TOKEN_INVALIDO: "No pudimos validar tu sesión. Ingresa nuevamente.",
  ACCESO_DENEGADO: "No tienes permisos para realizar esta acción.",
  CREDENCIALES_INVALIDAS: "El correo o la contraseña no son correctos.",
  DATOS_CONDOMINIO_INVALIDOS: "Algunos datos del condominio no son válidos. Revisa los campos marcados.",
  CONDOMINIO_NO_ENCONTRADO: "No encontramos el condominio solicitado.",
  VOUCHER_YA_CONCILIADO: "Este comprobante ya fue aprobado anteriormente. No necesitas reportarlo de nuevo.",
  VOUCHER_EN_EVALUACION: "Este comprobante ya fue reportado y está en revisión por la junta.",
  DEUDA_MORA_ACTIVA: "Tienes cuotas vencidas. Reporta tu pago para poder reservar áreas comunes.",
  CONFLICTO_HORARIO: "El área ya está reservada en ese horario. Elige otra franja.",
  LOTE_YA_EMITIDO: "Las cuotas de este periodo ya fueron emitidas.",
  PRESUPUESTO_NO_APROBADO: "Primero aprueba el presupuesto del periodo para emitir las cuotas.",
  ERROR_RED: "No pudimos conectar con el servidor. Revisa tu conexión e inténtalo de nuevo.",
};

export const MENSAJE_GENERICO = "Ocurrió un error inesperado. Inténtalo de nuevo en unos minutos.";

export interface ApiErrorPayload {
  error_code?: string;
  mensaje?: string;
  detalles?: unknown;
  detail?: { error_code?: string; mensaje?: string } | string;
}

/** Devuelve el mensaje en lenguaje claro para un código de error. */
export function mensajeParaCodigo(code: string | null | undefined, fallback?: string): string {
  if (code && MENSAJES[code]) return MENSAJES[code];
  return fallback || MENSAJE_GENERICO;
}

/** Extrae `{ code, message }` de cualquier forma de error que devuelve el backend. */
export function parseApiError(data: unknown, fallback?: string): { code: string | null; message: string } {
  if (!data || typeof data !== "object") {
    return { code: null, message: fallback || MENSAJE_GENERICO };
  }
  const payload = data as ApiErrorPayload;
  const detail = typeof payload.detail === "object" ? payload.detail : undefined;
  const code = payload.error_code || detail?.error_code || null;
  const serverMessage =
    payload.mensaje || detail?.mensaje || (typeof payload.detail === "string" ? payload.detail : undefined);
  return { code, message: code && MENSAJES[code] ? MENSAJES[code] : serverMessage || fallback || MENSAJE_GENERICO };
}
