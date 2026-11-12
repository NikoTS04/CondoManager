"""Pruebas Unitarias del Dominio de Notificaciones (Alejandro - PROC-03).

Valida:
1. Renderizado dinámico de plantillas.
2. Despacho exitoso y registro en bitácora.
3. Política de reintentos exponenciales (+2m, +10m, +30m) ante errores temporales.
4. Aborto inmediato de reintentos ante Hard Bounces (550).
5. Reenvío manual con corrección de contacto.
6. Despacho masivo a los 139 departamentos.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from src.modules.notificaciones.schemas import (
    CanalNotificacionEnum,
    DespacharNotificacionRequest,
    EnviarComunicadoMasivoRequest,
    EstadoNotificacionEnum,
)
from src.modules.notificaciones.service import NotificacionesService
from src.modules.notificaciones.templates import (
    PLANTILLAS_CONFIG,
    VARIABLES_OBLIGATORIAS,
    PlantillaIncompletaError,
    PlantillasService,
)


def test_renderizado_todas_las_plantillas():
    """Valida que todas las plantillas del catálogo se rendericen correctamente sin KeyError."""
    contexto_prueba = {
        "moneda": "S/",
        "costo": "35.00",
        "ajuste": "SIN_AJUSTE",
        "medios_pago": "Consulte los medios de pago vigentes con la administración.",
        "nombre": "Carlos Sánchez",
        "dpto": "502",
        "periodo": "2026-10",
        "monto": str(Decimal("150.00")),
        "vencimiento": "2026-10-20",
        "fecha_corte": "2026-10-20",
        "monto_pendiente": str(Decimal("150.00")),
        "banco": "BCP",
        "numero_operacion": "992812",
        "monto_abonado": str(Decimal("150.00")),
        "saldo_restante": str(Decimal("0.00")),
        "motivo_rechazo": "Comprobante no visible",
        "monto_mora": str(Decimal("20.00")),
        "fecha_local": "2026-10-11",
        "tipo_movimiento": "Cargo",
        "nuevo_saldo": str(Decimal("170.00")),
        "aviso_bloqueo_reservas": "Inhabilitado para reservar",
        "area": "Zona de Parrilla 1",
        "fecha": "2026-10-25",
        "horario": "19:00 - 22:00",
        "normas_convivencia": "Limpieza requerida",
        "motivo": "Cancelación por viaje",
        "titulo": "Corte de Agua Programado",
        "mensaje": "Se suspenderá el servicio de agua de 09:00 a 13:00 por mantenimiento.",
        "remitente": "Junta Directiva Villa Bonita 3",
    }

    for tipo_evento in PLANTILLAS_CONFIG.keys():
        asunto, cuerpo = PlantillasService.renderizar(tipo_evento, contexto_prueba)
        assert asunto is not None and len(asunto) > 0
        assert cuerpo is not None and len(cuerpo) > 0
        assert "{" not in asunto  # No quedaron placeholders sin sustituir
        assert "{" not in cuerpo


def test_plantilla_sin_variable_lanza_error_sin_filtrar_valores():
    contexto = {"nombre": "Secreto Confidencial", "dpto": "402", "moneda": "S/"}
    with pytest.raises(PlantillaIncompletaError) as exc:
        PlantillasService.renderizar("NOTIF_PAGO_CONCILIADO", contexto)
    assert exc.value.faltantes == ["monto_abonado", "saldo_restante"]
    assert "Secreto Confidencial" not in str(exc.value)
    assert isinstance(exc.value, ValueError)


@pytest.mark.parametrize("vacio", [None, "", "   "])
def test_variable_nula_o_vacia_cuenta_como_faltante(vacio):
    contexto = {
        "nombre": "Ana",
        "dpto": "101",
        "moneda": "S/",
        "monto_abonado": "10.00",
        "saldo_restante": vacio,
    }
    with pytest.raises(PlantillaIncompletaError) as exc:
        PlantillasService.renderizar("NOTIF_PAGO_CONCILIADO", contexto)
    assert exc.value.faltantes == ["saldo_restante"]


def test_tipo_desconocido_lanza_error_y_no_vuelca_el_contexto():
    with pytest.raises(PlantillaIncompletaError) as exc:
        PlantillasService.renderizar("NOTIF_INEXISTENTE", {"dato": "privado-123"})
    assert "privado-123" not in str(exc.value) and exc.value.faltantes == []


def test_variables_obligatorias_coinciden_con_los_placeholders():
    assert set(VARIABLES_OBLIGATORIAS) == set(PLANTILLAS_CONFIG)
    assert VARIABLES_OBLIGATORIAS["NOTIF_EMISION_CUOTA"] == sorted(
        ["dpto", "medios_pago", "moneda", "monto", "nombre", "periodo", "vencimiento"]
    )


def test_despacho_notificacion_exitoso():
    """Valida el flujo estándar de envío exitoso que pasa a estado ENTREGADO."""
    req = DespacharNotificacionRequest(
        condominio_id="vb3-condo",
        departamento_id="105",
        tipo_evento="NOTIF_PAGO_CONCILIADO",
        canal=CanalNotificacionEnum.EMAIL,
        destinatario="residente105@gmail.com",
        contexto={
            "nombre": "María Flores",
            "dpto": "105",
            "moneda": "S/",
            "monto_abonado": str(Decimal("150.00")),
            "saldo_restante": str(Decimal("0.00")),
        },
    )

    log = NotificacionesService.despachar_notificacion(req)

    assert log.estado == EstadoNotificacionEnum.ENTREGADO
    assert log.intentos == 1
    assert log.proveedor_message_id is not None
    assert log.error_mensaje is None
    assert "Su pago ha sido validado con éxito" in log.asunto


def test_reintento_automatico_error_temporal_503():
    """Valida que ante un error HTTP 503 temporal, el sistema programe el segundo intento para dentro de 2 min."""
    req = DespacharNotificacionRequest(
        condominio_id="vb3-condo",
        departamento_id="601",
        tipo_evento="NOTIF_MORA_APLICADA",
        canal=CanalNotificacionEnum.EMAIL,
        destinatario="residente601@gmail.com",
        contexto={
            "nombre": "Jorge Luna",
            "dpto": "601",
            "monto_mora": str(Decimal("20.00")),
            "nuevo_saldo": str(Decimal("170.00")),
            "aviso_bloqueo_reservas": "Inhabilitado para reservar áreas comunes",
        },
    )

    # Transporte que simula caída de servidor SMTP con 503
    def transport_con_falla_503(dest, canal, asunto, cuerpo):
        return {"status": 503, "error": "Service Unavailable"}

    ahora = datetime(2026, 10, 23, 8, 0, tzinfo=timezone.utc)
    log = NotificacionesService.despachar_notificacion(
        request=req,
        transport_fn=transport_con_falla_503,
        momento_actual=ahora,
    )

    assert log.estado == EstadoNotificacionEnum.REINTENTANDO
    assert log.intentos == 2
    assert log.proximo_reintento == ahora + timedelta(minutes=2)
    assert "Service Unavailable" in log.error_mensaje


def test_agotamiento_de_reintentos_hasta_fallido_permanente():
    """Valida que tras fallar el 4to intento, la notificación se marque como FALLIDO_PERMANENTE."""
    req = DespacharNotificacionRequest(
        condominio_id="vb3-condo",
        departamento_id="202",
        tipo_evento="NOTIF_EMISION_CUOTA",
        canal=CanalNotificacionEnum.EMAIL,
        destinatario="residente202@gmail.com",
        contexto={
            "nombre": "Lucía Gómez",
            "dpto": "202",
            "moneda": "S/",
            "periodo": "2026-10",
            "monto": "150.00",
            "vencimiento": "2026-10-20",
            "medios_pago": "Consulte los medios de pago vigentes con la administración.",
        },
    )

    log = NotificacionesService.despachar_notificacion(
        req, transport_fn=lambda *args, **kwargs: {"status": 500, "error": "Internal Error"}
    )
    assert log.estado == EstadoNotificacionEnum.REINTENTANDO
    assert log.intentos == 2  # Listo para intento 2

    # Falla intento 2 -> programa intento 3 (+10 min)
    ahora = datetime.now(timezone.utc)
    NotificacionesService.procesar_fallo(log, 500, "Internal Error", momento_actual=ahora)
    assert log.intentos == 3
    assert log.proximo_reintento == ahora + timedelta(minutes=10)

    # Falla intento 3 -> programa intento 4 (+30 min)
    NotificacionesService.procesar_fallo(log, 500, "Internal Error", momento_actual=ahora)
    assert log.intentos == 4
    assert log.proximo_reintento == ahora + timedelta(minutes=30)

    # Falla intento 4 (final) -> pasa a FALLIDO_PERMANENTE
    NotificacionesService.procesar_fallo(log, 500, "Internal Error", momento_actual=ahora)
    assert log.estado == EstadoNotificacionEnum.FALLIDO_PERMANENTE
    assert log.proximo_reintento is None


def test_hard_bounce_inmediato_550():
    """Valida que ante un error definitivo de buzón inexistente (550) aborte inmediatamente los reintentos."""
    req = DespacharNotificacionRequest(
        condominio_id="vb3-condo",
        departamento_id="402",
        tipo_evento="NOTIF_MORA_APLICADA",
        canal=CanalNotificacionEnum.EMAIL,
        destinatario="correo_falso_inexistente@gmail.com",
        contexto={
            "nombre": "Inexistente",
            "dpto": "402",
            "monto_mora": "20.00",
            "nuevo_saldo": "170.00",
            "aviso_bloqueo_reservas": "Inhabilitado para reservar áreas comunes",
        },
    )

    def transport_hard_bounce(dest, canal, asunto, cuerpo):
        return {"status": 550, "error": "550 User unknown / Mailbox does not exist"}

    log = NotificacionesService.despachar_notificacion(
        request=req,
        transport_fn=transport_hard_bounce,
    )

    assert log.estado == EstadoNotificacionEnum.FALLIDO_PERMANENTE
    assert log.intentos == 1  # No desperdicia reintentos
    assert log.proximo_reintento is None
    assert "User unknown" in log.error_mensaje


def test_reenviar_notificacion_manual_tras_correccion():
    """Valida que la administración pueda actualizar un correo rebotado y reenviarlo exitosamente."""
    req = DespacharNotificacionRequest(
        condominio_id="vb3-condo",
        departamento_id="402",
        tipo_evento="NOTIF_MORA_APLICADA",
        canal=CanalNotificacionEnum.EMAIL,
        destinatario="correo_erroneo@gmail.com",
        contexto={
            "nombre": "Residente 402",
            "dpto": "402",
            "monto_mora": "20.00",
            "nuevo_saldo": "170.00",
            "aviso_bloqueo_reservas": "Inhabilitado para reservar áreas comunes",
        },
    )

    # Primer intento rebotó
    log = NotificacionesService.despachar_notificacion(
        req, transport_fn=lambda *args, **kwargs: {"status": 550, "error": "User unknown"}
    )
    assert log.estado == EstadoNotificacionEnum.FALLIDO_PERMANENTE

    # Reenvío manual con correo corregido y transporte operativo
    log_actualizado = NotificacionesService.reenviar_notificacion_manual(
        log=log,
        nuevo_destinatario="nuevo_correo_correcto@gmail.com",
    )

    assert log_actualizado.destinatario == "nuevo_correo_correcto@gmail.com"
    assert log_actualizado.estado == EstadoNotificacionEnum.ENTREGADO
    assert log_actualizado.error_mensaje is None


def test_despacho_comunicado_masivo_139_departamentos():
    """Valida el envío de un comunicado oficial a los 139 departamentos de Villa Bonita 3."""
    from scripts.seed_condominio_piloto import generar_datos_departamentos

    deptos = generar_datos_departamentos()
    assert len(deptos) == 139
    for d in deptos:
        d["email_contacto"] = f"residente{d['numero']}@ejemplo.test"

    req_masivo = EnviarComunicadoMasivoRequest(
        condominio_id="vb3-condo",
        titulo="Corte de Luz Programado por Enel",
        mensaje="Se suspenderá la energía eléctrica en áreas comunes el sábado de 08:00 a 12:00.",
    )

    respuesta, logs = NotificacionesService.despachar_comunicado_masivo(
        request=req_masivo, departamentos=deptos
    )

    assert respuesta.generadas == 139
    assert respuesta.estado_general == "EN_COLA"
    assert len(logs) == 139
    assert all(log.estado == EstadoNotificacionEnum.EN_COLA and log.intentos == 0 for log in logs)
    assert all("Corte de Luz Programado por Enel" in log.asunto for log in logs)
