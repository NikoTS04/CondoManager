"""Pruebas BDD para el Dominio 03: Notificaciones y Comunicaciones Multicanal.

Ejecuta directamente el archivo de especificación en Gherkin:
specs/02-domains/03-notificaciones/features/notificaciones.feature
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import pytest

try:
    from pytest_bdd import given, parsers, scenarios, then, when
    HAS_PYTEST_BDD = True
except ImportError:
    HAS_PYTEST_BDD = False

from src.modules.notificaciones.schemas import (
    CanalNotificacionEnum,
    DespacharNotificacionRequest,
    EstadoNotificacionEnum,
)
from src.modules.notificaciones.service import NotificacionesService

FEATURE_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "specs"
    / "02-domains"
    / "03-notificaciones"
    / "features"
    / "notificaciones.feature"
)

if HAS_PYTEST_BDD and FEATURE_FILE.exists():
    scenarios(str(FEATURE_FILE))

    @pytest.fixture
    def context():
        return {}

    # Escenario 1: Envío automático de confirmación de pago validado
    @given(parsers.parse('que el residente del departamento "{depto}" tiene registrado el correo "{email}"'))
    def residente_con_correo(context, depto, email):
        context["depto"] = depto
        context["email"] = email

    @when(parsers.parse('la junta directiva aprueba el comprobante de pago del departamento "{depto}"'))
    def junta_aprueba_pago(context, depto):
        req = DespacharNotificacionRequest(
            condominio_id="vb3-condo",
            departamento_id=depto,
            tipo_evento="NOTIF_PAGO_CONCILIADO",
            canal=CanalNotificacionEnum.EMAIL,
            destinatario=context["email"],
            contexto={
                "nombre": f"Residente {depto}",
                "dpto": depto,
                "monto_abonado": str(Decimal("150.00")),
                "saldo_restante": str(Decimal("0.00")),
            },
        )
        context["log"] = NotificacionesService.despachar_notificacion(req)

    @then(parsers.parse('el despachador de notificaciones envía un correo con asunto "{asunto_esperado}"'))
    def verificar_asunto(context, asunto_esperado):
        assert context["log"].asunto == asunto_esperado

    @then(parsers.parse('el registro en "notificaciones_logs" queda en estado "{estado_esperado}" con intentos igual a {intentos:d}'))
    def verificar_registro_entregado(context, estado_esperado, intentos):
        assert context["log"].estado.value == estado_esperado
        assert context["log"].intentos == intentos

    # Escenario 2: Reintento automático tras caída temporal del servidor de correo
    @given(parsers.parse('que el sistema intenta despachar un aviso de mora al departamento "{depto}"'))
    def preparar_despacho_mora(context, depto):
        context["depto_mora"] = depto
        context["req_mora"] = DespacharNotificacionRequest(
            condominio_id="vb3-condo",
            departamento_id=depto,
            tipo_evento="NOTIF_MORA_APLICADA",
            canal=CanalNotificacionEnum.EMAIL,
            destinatario=f"residente{depto}@gmail.com",
            contexto={
                "nombre": f"Residente {depto}",
                "dpto": depto,
                "monto_mora": str(Decimal("20.00")),
                "nuevo_saldo": str(Decimal("170.00")),
            },
        )

    @given(parsers.parse('el servidor SMTP responde con error temporal {code:d} "{error_desc}"'))
    def mock_smtp_error_temporal(context, code, error_desc):
        context["status_code"] = code
        context["error_desc"] = error_desc

    @when('el worker de tareas asíncronas detecta el fallo')
    def worker_detecta_fallo(context):
        def transport_fallido(dest, canal, asunto, cuerpo):
            return {"status": context["status_code"], "error": context["error_desc"]}

        context["inicio_envio"] = datetime.now(timezone.utc)
        context["log_falla"] = NotificacionesService.despachar_notificacion(
            request=context["req_mora"],
            transport_fn=transport_fallido,
            momento_actual=context["inicio_envio"],
        )

    @then(parsers.parse('el estado de la notificación cambia a "{estado_esperado}"'))
    def verificar_estado_reintentando(context, estado_esperado):
        assert context["log_falla"].estado.value == estado_esperado

    @then('se programa un segundo intento para dentro de 2 minutos')
    def verificar_tiempo_segundo_intento(context):
        esperado = context["inicio_envio"] + timedelta(minutes=2)
        assert context["log_falla"].proximo_reintento == esperado

    @then(parsers.parse('el contador de intentos se incrementa a {intentos:d}'))
    def verificar_contador_intentos(context, intentos):
        assert context["log_falla"].intentos == intentos

else:
    def test_bdd_skipped_if_no_pytest_bdd():
        """Aviso informativo si pytest-bdd no está disponible."""
        if not HAS_PYTEST_BDD:
            pytest.skip("pytest-bdd no está instalado en el entorno de pruebas actual.")
