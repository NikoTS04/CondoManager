"""Pruebas BDD para el Dominio 03: Notificaciones y Comunicaciones Multicanal.

Ejecuta el archivo Gherkin `specs/02-domains/03-notificaciones/features/notificaciones.feature`
contra el motor persistente real (`repository.py`, `entrega.py`, `transportes.py`) sobre PostgreSQL.
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

try:
    from pytest_bdd import given, parsers, scenarios, then, when

    HAS_PYTEST_BDD = True
except ImportError:
    HAS_PYTEST_BDD = False

from src.modules.notificaciones.entrega import despachar_pendientes
from src.modules.notificaciones.models import Notificacion
from src.modules.notificaciones.repository import NuevaNotificacion, registrar_notificacion
from src.modules.notificaciones.transportes import ResultadoTransporte, TransporteSimulado
from src.modules.usuarios.piloto import CONDOMINIO_PILOTO_ID
from src.tests.integration.test_notificaciones_entrega_db import (
    _crear_base_notificaciones,
    borrar_base,
)

FEATURE_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "specs"
    / "02-domains"
    / "03-notificaciones"
    / "features"
    / "notificaciones.feature"
)


async def _registrar_y_despachar(
    base,
    nueva: NuevaNotificacion,
    transporte: TransporteSimulado,
    ahora: datetime,
) -> Notificacion:
    async with base.sessions() as session, session.begin():
        notif_id = await registrar_notificacion(session, nueva, ahora=ahora)
    assert notif_id is not None

    await despachar_pendientes(
        base.sessions,
        transporte,
        worker_id="bdd-worker",
        ahora=ahora,
        jitter_fn=lambda: 0.0,
    )

    async with base.sessions() as sesion_lectura:
        persistida = await sesion_lectura.get(Notificacion, notif_id)
        assert persistida is not None
        return persistida


if HAS_PYTEST_BDD and FEATURE_FILE.exists():
    scenarios(str(FEATURE_FILE))

    @pytest.fixture
    def bdd_db():
        url = (
            os.getenv("CON13_TEST_DATABASE_URL")
            or os.getenv("CON04_TEST_DATABASE_URL")
            or os.getenv("CON05_TEST_DATABASE_URL")
            or os.getenv("CON06_TEST_DATABASE_URL")
        )
        if not url:
            pytest.skip("Defina CON13_TEST_DATABASE_URL con una base PostgreSQL de pruebas.")
        base = asyncio.run(_crear_base_notificaciones(url))
        try:
            yield base
        finally:
            asyncio.run(borrar_base(base))

    @pytest.fixture
    def context(bdd_db):
        return {"db": bdd_db}

    @given(
        parsers.parse(
            'que el residente del departamento "{depto}" tiene registrado el correo "{email}"'
        )
    )
    def residente_con_correo(context, depto, email):
        context["depto"] = depto
        context["email"] = email

    @when(
        parsers.parse(
            'la junta directiva aprueba el comprobante de pago del departamento "{depto}"'
        )
    )
    def junta_aprueba_pago(context, depto):
        ahora = datetime.now(UTC)
        origen_id = uuid.uuid4()
        nueva = NuevaNotificacion(
            condominio_id=CONDOMINIO_PILOTO_ID,
            departamento_id=uuid.uuid5(CONDOMINIO_PILOTO_ID, depto),
            usuario_id=None,
            evento_id=uuid.uuid4(),
            tipo_evento="PagoRevisadoEvent",
            plantilla="NOTIF_PAGO_CONCILIADO",
            origen_tipo="COMPROBANTE",
            origen_id=origen_id,
            clave_deduplicacion=f"COMPROBANTE:{origen_id}:NOTIF_PAGO_CONCILIADO:EMAIL",
            canal="EMAIL",
            destinatario=context["email"],
            contexto={
                "nombre": f"Residente {depto}",
                "dpto": depto,
                "monto_abonado": str(Decimal("150.00")),
                "monto_aplicado": str(Decimal("150.00")),
                "saldo_restante": str(Decimal("0.00")),
                "saldo_resultante": str(Decimal("0.00")),
                "recibo_url": "https://app.condomanager.pe/recibos/rec-105.pdf",
            },
        )
        transporte = TransporteSimulado(confirmar_entrega=True)
        context["notificacion"] = asyncio.run(
            _registrar_y_despachar(context["db"], nueva, transporte, ahora)
        )

    @then(
        parsers.parse(
            'el despachador de notificaciones envía un correo con asunto "{asunto_esperado}"'
        )
    )
    def verificar_asunto(context, asunto_esperado):
        assert context["notificacion"].asunto == asunto_esperado

    @then(
        parsers.parse(
            'el registro en "notificaciones_logs" queda en estado "{estado_esperado}" '
            "con intentos igual a {intentos:d}"
        )
    )
    def verificar_registro_entregado(context, estado_esperado, intentos):
        notif = context["notificacion"]
        assert notif.estado == estado_esperado
        assert notif.intentos == intentos

    @given(
        parsers.parse(
            'que el sistema intenta despachar un aviso de mora al departamento "{depto}"'
        )
    )
    def preparar_despacho_mora(context, depto):
        origen_id = uuid.uuid4()
        context["nueva_mora"] = NuevaNotificacion(
            condominio_id=CONDOMINIO_PILOTO_ID,
            departamento_id=uuid.uuid5(CONDOMINIO_PILOTO_ID, depto),
            usuario_id=None,
            evento_id=uuid.uuid4(),
            tipo_evento="MoraAplicadaEvent",
            plantilla="NOTIF_MORA_APLICADA",
            origen_tipo="CUOTA",
            origen_id=origen_id,
            clave_deduplicacion=f"CUOTA:{origen_id}:NOTIF_MORA_APLICADA:EMAIL",
            canal="EMAIL",
            destinatario=f"residente{depto}@gmail.com",
            contexto={
                "nombre": f"Residente {depto}",
                "dpto": depto,
                "monto_mora": str(Decimal("20.00")),
                "nuevo_saldo": str(Decimal("170.00")),
                "aviso_bloqueo_reservas": "Inhabilitado para reservar áreas comunes",
            },
        )

    @given(parsers.parse('el servidor SMTP responde con error temporal {code:d} "{error_desc}"'))
    def mock_smtp_error_temporal(context, code, error_desc):
        context["status_code"] = code
        context["error_desc"] = error_desc

    @given(parsers.parse('el servidor SMTP responde con error definitivo {code:d} "{error_desc}"'))
    def mock_smtp_error_definitivo(context, code, error_desc):
        context["status_code"] = code
        context["error_desc"] = error_desc

    @when("el worker de tareas asíncronas detecta el fallo")
    def worker_detecta_fallo(context):
        ahora = datetime.now(UTC)
        context["inicio_envio"] = ahora
        transporte = TransporteSimulado(
            respuestas=[
                ResultadoTransporte.fallo(context["status_code"], context["error_desc"]),
            ]
        )
        context["notificacion_falla"] = asyncio.run(
            _registrar_y_despachar(context["db"], context["nueva_mora"], transporte, ahora)
        )

    @then(parsers.parse('el estado de la notificación cambia a "{estado_esperado}"'))
    def verificar_estado_reintentando(context, estado_esperado):
        assert context["notificacion_falla"].estado == estado_esperado

    @then("se programa un segundo intento para dentro de 2 minutos")
    def verificar_tiempo_segundo_intento(context):
        esperado = context["inicio_envio"] + timedelta(minutes=2)
        assert context["notificacion_falla"].proximo_intento_en == esperado

    @then("no se programa ningún próximo reintento")
    def verificar_sin_proximo_reintento(context):
        assert context["notificacion_falla"].proximo_intento_en is None

    @then(parsers.parse("el contador de intentos se incrementa a {intentos:d}"))
    def verificar_contador_intentos(context, intentos):
        notif = context["notificacion_falla"]
        assert notif.intentos + 1 == intentos

    @then(parsers.parse("el contador de intentos queda en {intentos:d}"))
    def verificar_contador_intentos_fijo(context, intentos):
        assert context["notificacion_falla"].intentos == intentos

else:

    def test_bdd_skipped_if_no_pytest_bdd():
        """Aviso informativo si pytest-bdd no está disponible."""
        if not HAS_PYTEST_BDD:
            pytest.skip("pytest-bdd no está instalado en el entorno de pruebas actual.")
