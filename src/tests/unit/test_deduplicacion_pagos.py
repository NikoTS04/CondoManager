"""Pruebas unitarias de deduplicación de comprobantes de pago (CON-23 / Brandon)."""

from datetime import date
from decimal import Decimal
import uuid
import pytest
from unittest.mock import AsyncMock, MagicMock
from sqlalchemy.exc import IntegrityError

from src.modules.pagos.models import ComprobantePago
from src.modules.pagos.schemas import ReportarPagoRequest
from src.modules.pagos.service import PagosService, VoucherDuplicadoException


def test_hash_idempotencia_normalizacion():
    """Verifica que variaciones de formato generen exactamente el mismo hash."""
    h1 = PagosService.calcular_hash_idempotencia(
        condominio_id="condo-01",
        banco="  bcp  ",
        numero_operacion="000123456",
        fecha_operacion=date(2026, 10, 20),
        monto=Decimal("250.00"),
    )
    h2 = PagosService.calcular_hash_idempotencia(
        condominio_id="condo-01",
        banco="BCP",
        numero_operacion="123456",
        fecha_operacion=date(2026, 10, 20),
        monto=Decimal("250.0000"),
    )
    assert h1 == h2
    assert len(h1) == 64


def test_reporte_nuevo_comprobante_en_memoria():
    """Un comprobante nuevo debe quedar registrado en estado EN_REVISION."""
    comprobantes = {}
    depto_id = uuid.uuid4()
    req = ReportarPagoRequest(
        departamento_id=depto_id,
        banco="Interbank",
        numero_operacion="789012",
        fecha_operacion=date(2026, 10, 21),
        monto=Decimal("180.50"),
        url_voucher="https://s3/vouchers/v1.png",
    )

    resp = PagosService.procesar_reporte_pago(req, "condo-01", comprobantes)

    assert resp.estado == "EN_REVISION"
    assert resp.comprobante_id is not None
    assert resp.idempotency_hash in comprobantes


def test_reintento_comprobante_en_revision_retorna_existente():
    """Reintentar el mismo comprobante aún en revisión no debe crear duplicados y debe retornar el original."""
    comprobantes = {}
    depto_id = uuid.uuid4()
    req = ReportarPagoRequest(
        departamento_id=depto_id,
        banco="BBVA",
        numero_operacion="445566",
        fecha_operacion=date(2026, 10, 21),
        monto=Decimal("300.00"),
        url_voucher="https://s3/vouchers/v2.jpg",
    )

    resp1 = PagosService.procesar_reporte_pago(req, "condo-01", comprobantes)
    resp2 = PagosService.procesar_reporte_pago(req, "condo-01", comprobantes)

    assert resp1.comprobante_id == resp2.comprobante_id
    assert resp1.idempotency_hash == resp2.idempotency_hash
    assert "previamente" in resp2.mensaje
    assert len(comprobantes) == 1


def test_rechazo_voucher_ya_conciliado():
    """Un voucher que ya fue aprobado/conciliado debe ser rechazado con 409 VOUCHER_YA_CONCILIADO."""
    comprobantes = {}
    depto_id = uuid.uuid4()
    req = ReportarPagoRequest(
        departamento_id=depto_id,
        banco="YAPE",
        numero_operacion="999888",
        fecha_operacion=date(2026, 10, 21),
        monto=Decimal("50.00"),
        url_voucher="https://s3/vouchers/yape.jpg",
    )

    resp1 = PagosService.procesar_reporte_pago(req, "condo-01", comprobantes)
    # Simular aprobación por la Junta Directiva
    comprobantes[resp1.idempotency_hash]["estado"] = "APROBADO"

    with pytest.raises(VoucherDuplicadoException) as exc_info:
        PagosService.procesar_reporte_pago(req, "condo-01", comprobantes)

    assert exc_info.value.error_code == "VOUCHER_YA_CONCILIADO"
    assert "ya fue conciliado" in exc_info.value.mensaje


def test_rechazo_voucher_reutilizado_en_otra_unidad():
    """Intentar usar el mismo voucher para otro departamento debe rechazarse con VOUCHER_UNIDAD_DISTINTA."""
    comprobantes = {}
    depto_1 = uuid.uuid4()
    depto_2 = uuid.uuid4()
    req1 = ReportarPagoRequest(
        departamento_id=depto_1,
        banco="PLIN",
        numero_operacion="112233",
        fecha_operacion=date(2026, 10, 21),
        monto=Decimal("120.00"),
        url_voucher="https://s3/vouchers/plin.jpg",
    )
    req2 = ReportarPagoRequest(
        departamento_id=depto_2,
        banco="PLIN",
        numero_operacion="112233",
        fecha_operacion=date(2026, 10, 21),
        monto=Decimal("120.00"),
        url_voucher="https://s3/vouchers/plin.jpg",
    )

    PagosService.procesar_reporte_pago(req1, "condo-01", comprobantes)

    with pytest.raises(VoucherDuplicadoException) as exc_info:
        PagosService.procesar_reporte_pago(req2, "condo-01", comprobantes)

    assert exc_info.value.error_code == "VOUCHER_UNIDAD_DISTINTA"
    assert "no puede aplicarse a otra unidad" in exc_info.value.mensaje


@pytest.mark.asyncio
async def test_flujo_persistente_con_repositorio_exitoso():
    """Valida el flujo asíncrono con PagosRepository cuando el registro es nuevo."""
    depto_id = uuid.uuid4()
    req = ReportarPagoRequest(
        departamento_id=depto_id,
        banco="BCP",
        numero_operacion="556677",
        fecha_operacion=date(2026, 10, 21),
        monto=Decimal("200.00"),
        url_voucher="https://s3/v1.png",
    )

    repo_mock = AsyncMock()
    repo_mock.buscar_por_hash.return_value = None
    repo_mock.guardar.side_effect = lambda c: c

    resp = await PagosService.procesar_reporte_pago_persistente(
        request=req,
        condominio_id="condo-01",
        repository=repo_mock,
    )

    assert resp.estado == "EN_REVISION"
    assert resp.comprobante_id is not None
    repo_mock.guardar.assert_awaited_once()


@pytest.mark.asyncio
async def test_flujo_persistente_carrera_concurrente_integrity_error():
    """Valida la resolución atómica ante una condición de carrera resuelta por IntegrityError en DB."""
    depto_id = uuid.uuid4()
    req = ReportarPagoRequest(
        departamento_id=depto_id,
        banco="BCP",
        numero_operacion="778899",
        fecha_operacion=date(2026, 10, 21),
        monto=Decimal("350.00"),
        url_voucher="https://s3/v3.png",
    )

    comprobante_existente = ComprobantePago(
        id=uuid.uuid4(),
        departamento_id=depto_id,
        banco_origen="BCP",
        numero_operacion="778899",
        fecha_operacion=date(2026, 10, 21),
        monto=Decimal("350.00"),
        url_voucher="https://s3/v3.png",
        idempotency_hash="hash-123",
        estado="EN_REVISION",
    )

    repo_mock = AsyncMock()
    # Primera consulta dice que no existe
    # Al intentar guardar, otro proceso se adelantó y lanza IntegrityError
    # La segunda consulta recupera el registro ganador
    repo_mock.buscar_por_hash.side_effect = [None, comprobante_existente]
    repo_mock.guardar.side_effect = IntegrityError("duplicate key", None, None)

    resp = await PagosService.procesar_reporte_pago_persistente(
        request=req,
        condominio_id="condo-01",
        repository=repo_mock,
    )

    assert resp.comprobante_id == comprobante_existente.id
    assert resp.estado == "EN_REVISION"
    assert "previamente" in resp.mensaje
