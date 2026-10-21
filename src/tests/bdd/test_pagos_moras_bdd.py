"""Pruebas BDD para el Dominio 02: Pagos, Moras y Deduplicación (CON-23 / Brandon)."""

import uuid
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

try:
    from pytest_bdd import given, parsers, scenarios, then, when

    HAS_PYTEST_BDD = True
except ImportError:
    HAS_PYTEST_BDD = False

from src.modules.pagos.moras_service import MotorMorasService
from src.modules.pagos.schemas import ReportarPagoRequest
from src.modules.pagos.service import PagosService, VoucherDuplicadoException

FEATURE_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "specs"
    / "02-domains"
    / "02-pagos-y-moras"
    / "features"
    / "pagos_y_moras.feature"
)

if HAS_PYTEST_BDD and FEATURE_FILE.exists():
    scenarios(str(FEATURE_FILE))

    @pytest.fixture
    def context():
        return {
            "comprobantes": {},
            "cuotas": [],
            "departamentos": {},
            "comprobantes_en_revision": {},
            "error": None,
        }

    # Escenario 1: Moras
    @given(
        parsers.parse(
            'que el departamento "{depto}" tiene una cuota vencida de "{monto}" soles con fecha de vencimiento "{fecha}"'
        )
    )
    def cuota_vencida(context, depto, monto, fecha):
        depto_id = uuid.uuid4()
        context["depto_id"] = depto_id
        context["depto_nombre"] = depto
        context["departamentos"][depto_id] = {"id": depto_id, "estado_financiero": "AL_DIA"}
        y, m, d = map(int, fecha.split("-"))
        context["cuotas"].append(
            {
                "id": uuid.uuid4(),
                "departamento_id": depto_id,
                "periodo": "2026-10",
                "monto_total_exigible": Decimal(monto),
                "monto_pagado": Decimal("0.00"),
                "monto_mora": Decimal("0.00"),
                "fecha_vencimiento": date(y, m, d),
                "estado": "EMITIDA",
            }
        )

    @given(parsers.parse("el periodo de gracia configurado es de {dias:d} días calendario"))
    def periodo_gracia(context, dias):
        context["dias_gracia"] = dias

    @given("el residente no ha reportado ningún comprobante de pago")
    def sin_comprobante(context):
        context["comprobantes_en_revision"] = {}

    @when(
        parsers.parse('el evaluador nocturno de moras se ejecuta el "{fecha}" a las {hora} horas')
    )
    def ejecutar_evaluador(context, fecha, hora):
        y, m, d = map(int, fecha.split("-"))
        MotorMorasService.evaluar_y_aplicar_moras(
            cuotas=context["cuotas"],
            departamentos=context["departamentos"],
            comprobantes_en_revision_por_depto=context["comprobantes_en_revision"],
            fecha_evaluacion=date(y, m, d),
            dias_gracia=context.get("dias_gracia", 2),
            monto_mora_fijo=Decimal("20.00"),
        )

    @then(parsers.parse('el estado de la cuota cambia a "{estado}"'))
    def verificar_estado_cuota(context, estado):
        assert context["cuotas"][0]["estado"] == estado

    @then(parsers.parse('se agrega un recargo por mora de "{monto}" soles'))
    def verificar_recargo_mora(context, monto):
        assert context["cuotas"][0]["monto_mora"] == Decimal(monto)

    @then(
        parsers.parse('el total exigible del departamento "{depto}" pasa a ser de "{total}" soles')
    )
    def verificar_total_exigible(context, depto, total):
        assert context["cuotas"][0]["monto_total_exigible"] == Decimal(total)

    @then("el departamento queda inhabilitado para reservar áreas comunes")
    def verificar_depto_inhabilitado(context):
        depto_id = context["depto_id"]
        assert context["departamentos"][depto_id]["estado_financiero"] == "EN_MORA"

    # Escenario 2: Deduplicación CON-23 (Brandon)
    @given(
        parsers.parse(
            'que existe un comprobante previamente aprobado en el banco "{banco}" con operacion "{op}" por "{monto}" soles'
        )
    )
    def comprobante_aprobado_previo(context, banco, op, monto):
        depto_id = uuid.uuid4()
        context["depto_id"] = depto_id
        req = ReportarPagoRequest(
            departamento_id=depto_id,
            banco=banco,
            numero_operacion=op,
            fecha_operacion=date(2026, 10, 15),
            monto=Decimal(monto),
        )
        resp = PagosService.procesar_reporte_pago(req, "condo-01", context["comprobantes"])
        context["comprobantes"][resp.idempotency_hash]["estado"] = "APROBADO"
        context["cantidad_inicial"] = len(context["comprobantes"])

    @when(
        parsers.parse(
            'un residente intenta registrar nuevamente un voucher con banco "{banco}" y operacion "{op}"'
        )
    )
    def registrar_nuevamente_voucher(context, banco, op):
        req = ReportarPagoRequest(
            departamento_id=context["depto_id"],
            banco=banco,
            numero_operacion=op,
            fecha_operacion=date(2026, 10, 15),
            monto=Decimal("150.00"),
        )
        try:
            PagosService.procesar_reporte_pago(req, "condo-01", context["comprobantes"])
        except VoucherDuplicadoException as exc:
            context["error"] = exc

    @then(parsers.parse('el sistema rechaza la solicitud con código de error "{error_code}"'))
    def verificar_error_rechazo(context, error_code):
        assert context["error"] is not None
        assert context["error"].error_code == error_code

    @then("no se crea ningún registro duplicado en la base de datos")
    def verificar_sin_duplicados(context):
        assert len(context["comprobantes"]) == context["cantidad_inicial"]

    # Escenario 3: Imputación en prelación
    @given(
        parsers.parse('que el departamento "{depto}" mantiene una cuota vencida de "{monto}" soles')
    )
    def cuota_vencida_depto(context, depto, monto):
        depto_id = uuid.uuid4()
        context["depto_id"] = depto_id
        context["departamento"] = {
            "id": depto_id,
            "saldo_a_favor": Decimal("0.00"),
            "estado_financiero": "EN_MORA",
        }
        context["cuotas_pendientes"] = [
            {
                "id": uuid.uuid4(),
                "fecha_vencimiento": date(2026, 9, 20),
                "monto_total_exigible": Decimal(monto),
                "monto_pagado": Decimal("0.00"),
                "estado": "EN_MORA",
            }
        ]

    @when(parsers.parse('la junta directiva aprueba un comprobante reportado por "{monto}" soles'))
    def aprobar_comprobante(context, monto):
        comprobante = {
            "id": uuid.uuid4(),
            "departamento_id": context["depto_id"],
            "banco_origen": "BCP",
            "monto": Decimal(monto),
        }
        context["resultado_conciliacion"] = PagosService.conciliar_comprobante(
            comprobante=comprobante,
            decision="APROBADO",
            cuotas_pendientes=context["cuotas_pendientes"],
            departamento=context["departamento"],
        )

    @then(parsers.parse('la cuota vencida pasa al estado "{estado}"'))
    def verificar_estado_final_cuota(context, estado):
        assert context["cuotas_pendientes"][0]["estado"] == estado

    @then(
        parsers.parse(
            'el remanente de "{monto}" soles se asigna automáticamente al "{campo}" del departamento "{depto}"'
        )
    )
    def verificar_remanente_saldo(context, monto, campo, depto):
        assert context["departamento"][campo] == Decimal(monto)
