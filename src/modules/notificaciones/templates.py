"""Catálogo y Motor de Renderizado de Plantillas de Notificaciones (Alejandro - PROC-03).

Implementa la matriz de plantillas dinámicas según specs/02-domains/03-notificaciones/spec.md.
"""

from string import Formatter
from typing import Any, Dict, Tuple

PLANTILLAS_CONFIG = {
    "NOTIF_MORA_DIARIA": {
        "asunto": "CondoManager: {tipo_movimiento} de mora diaria",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "{tipo_movimiento} correspondiente al {fecha_local}: {moneda} {monto_mora}.\n"
            "Saldo pendiente al registrar el movimiento: {moneda} {nuevo_saldo}.\n"
            "Los ajustes conservan el historial y consideran la fecha bancaria validada.\n"
            "Atentamente,\nAdministración"
        ),
    },
    "NOTIF_EMISION_CUOTA": {
        "asunto": "CondoManager: Emisión de cuota de mantenimiento - Periodo {periodo}",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Se ha emitido la cuota de mantenimiento ordinaria correspondiente al periodo {periodo}.\n"
            "• Monto a pagar: {moneda} {monto}\n"
            "• Fecha límite de vencimiento: {vencimiento}\n"
            "• Medios de pago: {medios_pago}\n\n"
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
            "Hemos recibido su comprobante de pago por {moneda} {monto} (Op. {numero_operacion} - {banco}).\n"
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
            "• Monto abonado: {moneda} {monto_abonado}\n"
            "• Saldo restante del departamento: {moneda} {saldo_restante}\n"
            "Puede consultar el detalle en su historial de pagos.\n\n"
            "Gracias por su compromiso y puntualidad con el edificio.\n"
            "Atentamente,\nJunta Directiva"
        ),
    },
    "NOTIF_PAGO_RECHAZADO": {
        "asunto": "CondoManager: Comprobante de pago rechazado",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n\n"
            "Su comprobante de pago ha sido rechazado por la Junta Directiva.\n"
            "• Motivo: {motivo_rechazo}\n"
            "Contacte con la administración para revisar los datos; no vuelva a reportar la misma operación.\n"
            "Atentamente,\nJunta Directiva"
        ),
    },
    "NOTIF_PAGO_OBSERVADO": {
        "asunto": "CondoManager: Comprobante de pago observado",
        "cuerpo": (
            "Estimado(a) {nombre} (Dpto. {dpto}):\n"
            "Su comprobante requiere revisión. Motivo: {motivo_rechazo}\n"
            "Para subsanarlo, adjunte un nuevo archivo con la opción Subsanar voucher de su historial de pagos.\n"
            "No se han aplicado saldos por esta observación."
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
            "• Tarifa confirmada: {moneda} {costo}\n"
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
            "• Ajuste económico: {ajuste}\n\n"
            "El horario ha sido liberado para otros residentes de la comunidad.\n"
            "Atentamente,\nAdministración"
        ),
    },
    "NOTIF_COMUNICADO_GENERAL": {
        "asunto": "CondoManager Comunicado: {titulo}",
        "cuerpo": ("COMUNICADO OFICIAL DE LA COMUNIDAD\n\n{mensaje}\n\nEmitido por: {remitente}"),
    },
}


class PlantillaIncompletaError(ValueError):
    """Plantilla desconocida o sin todas sus variables; el mensaje nunca incluye valores."""

    def __init__(self, tipo_evento: str, faltantes: list[str] | None = None):
        self.tipo_evento = tipo_evento
        self.faltantes = sorted(faltantes or [])
        detalle = (
            f"Faltan variables: {', '.join(self.faltantes)}."
            if self.faltantes
            else "Tipo de plantilla no soportado."
        )
        super().__init__(f"Plantilla {tipo_evento} incompleta. {detalle}")


def _campos(texto: str) -> set[str]:
    return {nombre for _, nombre, _, _ in Formatter().parse(texto) if nombre}


# Variables obligatorias derivadas de los placeholders de cada plantilla.
VARIABLES_OBLIGATORIAS = {
    tipo: sorted(_campos(config["asunto"]) | _campos(config["cuerpo"]))
    for tipo, config in PLANTILLAS_CONFIG.items()
}


class PlantillasService:
    @staticmethod
    def variables_requeridas(tipo_evento: str) -> list[str]:
        if tipo_evento not in VARIABLES_OBLIGATORIAS:
            raise PlantillaIncompletaError(tipo_evento)
        return list(VARIABLES_OBLIGATORIAS[tipo_evento])

    @staticmethod
    def renderizar(tipo_evento: str, contexto: Dict[str, Any]) -> Tuple[str, str]:
        """Renderiza asunto y cuerpo; no completa ningún dato que falte con valores por defecto."""
        requeridas = PlantillasService.variables_requeridas(tipo_evento)
        contexto = contexto or {}
        faltantes = [
            nombre
            for nombre in requeridas
            if contexto.get(nombre) is None or str(contexto[nombre]).strip() == ""
        ]
        if faltantes:
            raise PlantillaIncompletaError(tipo_evento, faltantes)
        config = PLANTILLAS_CONFIG[tipo_evento]
        valores = {nombre: contexto[nombre] for nombre in requeridas}
        return config["asunto"].format(**valores), config["cuerpo"].format(**valores)
