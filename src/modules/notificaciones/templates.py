"""Catálogo y motor de renderizado de plantillas de notificaciones (Alejandro - PROC-03).

Valida variables obligatorias por plantilla y prohíbe valores por defecto
financieros o de negocio (montos, saldos, motivos, departamentos o fechas).
"""

from decimal import Decimal, InvalidOperation
from typing import Any

from src.shared.decimal_types import redondear_moneda

CAMPOS_MONETARIOS = frozenset(
    {
        "monto",
        "monto_total_exigible",
        "monto_pendiente",
        "monto_abonado",
        "monto_aplicado",
        "saldo_restante",
        "saldo_resultante",
        "monto_mora",
        "nuevo_saldo",
        "costo",
        "costo_reserva",
        "monto_reembolso",
    }
)

VALORES_NO_FINANCIEROS_POR_DEFECTO: dict[str, str] = {
    "nombre": "Residente",
    "recibo_url": "https://app.condomanager.pe/recibos/",
    "enlace_subir_nuevo": "https://app.condomanager.pe/pagos/reportar",
    "aviso_bloqueo_reservas": "Inhabilitado para reservar áreas comunes",
    "instrucciones": "Por favor revise la información y vuelva a cargar una evidencia legible.",
    "ajuste_economico": "Sin ajuste económico aplicable",
    "remitente": "Junta Directiva",
}


class PlantillaError(ValueError, KeyError):
    """Error de validación o renderizado de plantilla."""

    def __str__(self) -> str:
        return ValueError.__str__(self)


class PlantillaNoEncontradaError(PlantillaError):
    """La plantilla solicitada no existe en el catálogo."""


class PlantillaVariableFaltanteError(PlantillaError):
    """Faltan variables obligatorias para renderizar la plantilla."""


PLANTILLAS_CONFIG: dict[str, dict[str, Any]] = {
    "NOTIF_EMISION_CUOTA": {
        "requeridas": ("dpto", "periodo", "monto", "vencimiento"),
        "asunto": "CondoManager: Emisión de cuota de mantenimiento - Periodo {periodo}",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Se ha emitido la cuota de mantenimiento ordinaria correspondiente al periodo {periodo}.\n"
            "• Monto a pagar: S/ {monto}\n"
            "• Saldo pendiente: S/ {monto_pendiente}\n"
            "• Fecha límite de vencimiento: {vencimiento}\n"
            "• Medios de pago: {cci_banco}\n\n"
            "Recuerde subir su comprobante una vez efectuado el abono desde la plataforma.\n"
            "Atentamente,\nJunta Directiva"
        ),
    },
    "NOTIF_RECORDATORIO_PREVIO": {
        "requeridas": ("dpto", "fecha_corte", "monto_pendiente"),
        "asunto": "CondoManager: Recordatorio amistoso de vencimiento próximo",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Le recordamos que el plazo para el pago oportuno de su cuota vence el {fecha_corte}.\n"
            "• Saldo pendiente: S/ {monto_pendiente}\n\n"
            "Evite recargos por mora y restricciones de reserva de áreas comunes.\n"
            "Atentamente,\nAdministración"
        ),
    },
    "NOTIF_PAGO_RECIBIDO": {
        "requeridas": ("dpto", "monto", "numero_operacion", "banco"),
        "asunto": "CondoManager: Hemos recibido su comprobante de pago",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Hemos recibido su comprobante de pago por S/ {monto} (Op. {numero_operacion} - {banco}).\n"
            "Su comprobante ha ingresado en cola de revisión para conciliación bancaria.\n"
            "Le avisaremos tan pronto sea validado.\n\n"
            "Atentamente,\nJunta Directiva"
        ),
    },
    "NOTIF_PAGO_CONCILIADO": {
        "requeridas": ("dpto", "monto_abonado", "saldo_restante"),
        "asunto": "CondoManager: Su pago ha sido validado con éxito",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Nos complace informarle que su comprobante de pago ha sido validado y conciliado con éxito.\n"
            "• Monto abonado: S/ {monto_abonado}\n"
            "• Saldo restante del departamento: S/ {saldo_restante}\n"
            "• Comprobante digital: {recibo_url}\n\n"
            "Gracias por su compromiso y puntualidad con el edificio.\n"
            "Atentamente,\nJunta Directiva"
        ),
    },
    "NOTIF_PAGO_OBSERVADO": {
        "requeridas": ("dpto", "motivo", "instrucciones"),
        "asunto": "CondoManager: Observación en comprobante de pago reportado",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Su comprobante de pago reportado presenta una observación pendiente de subsanación.\n"
            "• Motivo: {motivo}\n"
            "• Instrucciones de subsanación: {instrucciones}\n"
            "• Enlace para subsanar: {enlace_subir_nuevo}\n\n"
            "Por favor revise las indicaciones y adjunte la evidencia corregida en la plataforma.\n"
            "Atentamente,\nJunta Directiva"
        ),
    },
    "NOTIF_PAGO_RECHAZADO": {
        "requeridas": ("dpto", "motivo_rechazo"),
        "asunto": "CondoManager: Observación en comprobante de pago reportado",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Su comprobante de pago reportado ha sido observado o rechazado por la Junta Directiva.\n"
            "• Motivo: {motivo_rechazo}\n"
            "• Instrucciones: {instrucciones}\n"
            "• Enlace para adjuntar un nuevo comprobante legible: {enlace_subir_nuevo}\n\n"
            "Por favor revise la información y vuelva a cargar una imagen clara de la transferencia.\n"
            "Atentamente,\nJunta Directiva"
        ),
    },
    "NOTIF_MORA_APLICADA": {
        "requeridas": ("dpto", "monto_mora", "nuevo_saldo"),
        "asunto": "CondoManager: Notificación de aplicación de mora por cuota vencida",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Habiendo vencido el periodo de gracia reglamentario sin registrar pago, "
            "se ha aplicado un recargo por mora de S/ {monto_mora}.\n"
            "• Nuevo saldo total exigible: S/ {nuevo_saldo}\n"
            "• Estado de reservas: {aviso_bloqueo_reservas}\n\n"
            "Para rehabilitar su acceso a áreas comunes, por favor cancele la deuda y suba su voucher a la brevedad.\n"
            "Atentamente,\nAdministración"
        ),
    },
    "NOTIF_RESERVA_CONFIRMADA": {
        "requeridas": ("dpto", "area", "fecha", "horario", "costo", "normas_convivencia"),
        "asunto": "CondoManager: Confirmación de reserva de área común",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Su solicitud de reserva ha sido aprobada y confirmada exitosamente.\n"
            "• Espacio: {area}\n"
            "• Fecha: {fecha}\n"
            "• Horario: {horario}\n"
            "• Costo: S/ {costo}\n"
            "• Normas de uso: {normas_convivencia}\n\n"
            "Le recordamos mantener el orden y cuidar las instalaciones.\n"
            "Atentamente,\nAdministración"
        ),
    },
    "NOTIF_RESERVA_CANCELADA": {
        "requeridas": ("dpto", "area", "fecha", "horario", "motivo"),
        "asunto": "CondoManager: Cancelación de reserva de área común",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Se confirma la cancelación de su reserva para el espacio {area} el {fecha} ({horario}).\n"
            "• Motivo: {motivo}\n"
            "• Ajuste económico: {ajuste_economico}\n\n"
            "El horario ha sido liberado para otros residentes de la comunidad.\n"
            "Atentamente,\nAdministración"
        ),
    },
    "NOTIF_COMUNICADO_GENERAL": {
        "requeridas": ("titulo", "mensaje"),
        "asunto": "CondoManager Comunicado: {titulo}",
        "cuerpo": (
            "COMUNICADO OFICIAL DE LA COMUNIDAD\n\n"
            "{mensaje}\n\n"
            "Emitido por: {remitente}"
        ),
    },
}


def _formatear_importe(campo: str, valor: Any) -> str:
    if isinstance(valor, float):
        raise PlantillaError(
            f"El campo monetario '{campo}' no permite float; use Decimal o cadena decimal."
        )
    if isinstance(valor, Decimal):
        return f"{redondear_moneda(valor):.2f}"
    if isinstance(valor, int):
        return f"{Decimal(valor):.2f}"
    if isinstance(valor, str):
        texto = valor.strip()
        if not texto:
            raise PlantillaVariableFaltanteError(f"El campo monetario '{campo}' está vacío.")
        try:
            return f"{redondear_moneda(Decimal(texto)):.2f}"
        except InvalidOperation as exc:
            raise PlantillaError(
                f"El campo monetario '{campo}' tiene un valor decimal inválido: {valor!r}"
            ) from exc
    raise PlantillaError(f"Tipo inválido para campo monetario '{campo}': {type(valor).__name__}")


def _normalizar_contexto(tipo_evento: str, contexto: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(contexto, dict):
        raise PlantillaError("El contexto de la plantilla debe ser un diccionario.")

    datos: dict[str, Any] = {}
    for clave, valor in contexto.items():
        if valor is None:
            continue
        if isinstance(valor, str) and not valor.strip():
            continue
        if clave in CAMPOS_MONETARIOS:
            datos[clave] = _formatear_importe(clave, valor)
        else:
            datos[clave] = valor

    # Sinónimos de contrato para mantener consistencia entre eventos y plantillas
    pares_sinonimos = (
        ("departamento", "dpto"),
        ("monto_aplicado", "monto_abonado"),
        ("saldo_resultante", "saldo_restante"),
        ("medios_pago", "cci_banco"),
        ("fecha_reserva", "fecha"),
        ("costo_reserva", "costo"),
        ("normas", "normas_convivencia"),
    )
    for origen, destino in pares_sinonimos:
        if origen in datos and destino not in datos:
            datos[destino] = datos[origen]
        elif destino in datos and origen not in datos:
            datos[origen] = datos[destino]

    if tipo_evento == "NOTIF_PAGO_RECHAZADO":
        if "motivo" in datos and "motivo_rechazo" not in datos:
            datos["motivo_rechazo"] = datos["motivo"]
    elif tipo_evento == "NOTIF_PAGO_OBSERVADO":
        if "motivo_rechazo" in datos and "motivo" not in datos:
            datos["motivo"] = datos["motivo_rechazo"]

    if tipo_evento == "NOTIF_EMISION_CUOTA":
        if "monto_total_exigible" in datos and "monto" not in datos:
            datos["monto"] = datos["monto_total_exigible"]
        if "monto" in datos and "monto_pendiente" not in datos:
            datos["monto_pendiente"] = datos["monto"]

    if tipo_evento == "NOTIF_RESERVA_CANCELADA":
        if "monto_reembolso" in datos and "ajuste_economico" not in datos:
            datos["ajuste_economico"] = f"Reembolso / ajuste aplicable: S/ {datos['monto_reembolso']}"

    return datos


class PlantillasService:
    @staticmethod
    def renderizar(tipo_evento: str, contexto: dict[str, Any]) -> tuple[str, str]:
        """Renderiza asunto y cuerpo validando que estén presentes todas las variables requeridas."""
        config = PLANTILLAS_CONFIG.get(tipo_evento)
        if not config:
            raise PlantillaNoEncontradaError(f"Plantilla no registrada: {tipo_evento}")

        datos = _normalizar_contexto(tipo_evento, contexto)
        requeridas: tuple[str, ...] = config.get("requeridas", ())
        faltantes = [
            campo
            for campo in requeridas
            if campo not in datos or str(datos[campo]).strip() == ""
        ]
        if faltantes:
            lista = ", ".join(faltantes)
            raise PlantillaVariableFaltanteError(
                f"Faltan variables requeridas en plantilla {tipo_evento}: {lista}"
            )

        contexto_render = dict(VALORES_NO_FINANCIEROS_POR_DEFECTO)
        if tipo_evento == "NOTIF_PAGO_OBSERVADO":
            # En NOTIF_PAGO_OBSERVADO, instrucciones es estrictamente requerida (validada arriba)
            contexto_render.pop("instrucciones", None)
        contexto_render.update(datos)

        asunto = config["asunto"].format(**contexto_render)
        cuerpo = config["cuerpo"].format(**contexto_render)
        return asunto, cuerpo
