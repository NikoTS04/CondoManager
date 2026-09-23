"""Catálogo y Motor de Renderizado de Plantillas de Notificaciones (Alejandro - PROC-03).

Implementa la matriz de plantillas dinámicas según specs/02-domains/03-notificaciones/spec.md.
"""

from typing import Any, Dict, Tuple


PLANTILLAS_CONFIG = {
    "NOTIF_EMISION_CUOTA": {
        "asunto": "CondoManager: Emisión de cuota de mantenimiento - Periodo {periodo}",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Se ha emitido la cuota de mantenimiento ordinaria correspondiente al periodo {periodo}.\n"
            "• Monto a pagar: S/ {monto}\n"
            "• Fecha límite de vencimiento: {vencimiento}\n"
            "• Cuenta de recaudación / CCI: {cci_banco}\n\n"
            "Recuerde subir su comprobante una vez efectuado el abono desde la plataforma.\n"
            "Atentamente,\nJunta Directiva"
        ),
    },
    "NOTIF_RECORDATORIO_PREVIO": {
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
    "NOTIF_PAGO_RECHAZADO": {
        "asunto": "CondoManager: Observación en comprobante de pago reportado",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Su comprobante de pago reportado ha sido observado o rechazado por la Junta Directiva.\n"
            "• Motivo: {motivo_rechazo}\n"
            "• Enlace para adjuntar un nuevo comprobante legible: {enlace_subir_nuevo}\n\n"
            "Por favor revise la información y vuelva a cargar una imagen clara de la transferencia.\n"
            "Atentamente,\nJunta Directiva"
        ),
    },
    "NOTIF_MORA_APLICADA": {
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
        "asunto": "CondoManager: Confirmación de reserva de área común",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Su solicitud de reserva ha sido aprobada y confirmada exitosamente.\n"
            "• Espacio: {area}\n"
            "• Fecha: {fecha}\n"
            "• Horario: {horario}\n"
            "• Normas de uso: {normas_convivencia}\n\n"
            "Le recordamos mantener el orden y cuidar las instalaciones.\n"
            "Atentamente,\nAdministración"
        ),
    },
    "NOTIF_RESERVA_CANCELADA": {
        "asunto": "CondoManager: Cancelación de reserva de área común",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Se confirma la cancelación de su reserva para el espacio {area} el {fecha} ({horario}).\n"
            "• Motivo: {motivo}\n\n"
            "El horario ha sido liberado para otros residentes de la comunidad.\n"
            "Atentamente,\nAdministración"
        ),
    },
    "NOTIF_COMUNICADO_GENERAL": {
        "asunto": "CondoManager Comunicado: {titulo}",
        "cuerpo": (
            "COMUNICADO OFICIAL DE LA COMUNIDAD\n\n"
            "{mensaje}\n\n"
            "Emitido por: {remitente}"
        ),
    },
}


class PlantillasService:
    @staticmethod
    def renderizar(tipo_evento: str, contexto: Dict[str, Any]) -> Tuple[str, str]:
        """Renderiza de forma segura el asunto y el cuerpo de una plantilla inyectando variables de contexto."""
        config = PLANTILLAS_CONFIG.get(tipo_evento)
        if not config:
            asunto = f"CondoManager Notificación: {tipo_evento}"
            cuerpo = str(contexto)
            return asunto, cuerpo

        # Valores por defecto seguros para evitar KeyErrors
        contexto_seguro = {
            "nombre": "Residente",
            "dpto": "-",
            "periodo": "-",
            "monto": "0.00",
            "vencimiento": "-",
            "cci_banco": "002-191-000000000000-54",
            "fecha_corte": "-",
            "monto_pendiente": "0.00",
            "banco": "BANCO",
            "numero_operacion": "000000",
            "monto_abonado": "0.00",
            "saldo_restante": "0.00",
            "recibo_url": "https://app.condomanager.pe/recibos/",
            "motivo_rechazo": "Comprobante no coincide con extracto",
            "enlace_subir_nuevo": "https://app.condomanager.pe/pagos/reportar",
            "monto_mora": "20.00",
            "nuevo_saldo": "0.00",
            "aviso_bloqueo_reservas": "Inhabilitado para reservar áreas comunes",
            "area": "Área Común",
            "fecha": "-",
            "horario": "-",
            "normas_convivencia": "Aforo máximo respetado y limpieza obligatoria",
            "motivo": "Cancelación solicitada",
            "titulo": "Comunicado General",
            "mensaje": "",
            "remitente": "Junta Directiva",
        }
        contexto_seguro.update(contexto)

        asunto = config["asunto"].format(**contexto_seguro)
        cuerpo = config["cuerpo"].format(**contexto_seguro)
        return asunto, cuerpo
