"""Pruebas de contrato/modelo sin base PostgreSQL ni infraestructura externa."""

from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import configure_mappers

# La conftest del proyecto carga src.main y sus modelos base antes de los tests.
from src.modules.egresos.models import (
    AperturaCaja,
    AprobacionEgreso,
    ConfiguracionAprobacionEgreso,
    CuentaCaja,
    DocumentoFinanciero,
    Egreso,
    HistorialEgreso,
    MovimientoCaja,
    PagoEgreso,
    ReversoPago,
)
from src.modules.egresos.schemas import (
    ConfigurarAprobacionRequest,
    CrearEgresoRequest,
    EstadoEgreso,
    RegistrarAperturaCajaRequest,
    RegistrarAprobacionRequest,
)


def test_mapeadores_y_tablas_de_egresos_se_configuran():
    configure_mappers()
    assert {
        "egresos",
        "documentos_financieros",
        "aprobaciones_egreso",
        "historial_egreso",
        "configuracion_aprobacion_egreso",
        "pagos_egreso",
        "reversos_pago_egreso",
        "cuentas_caja",
        "aperturas_caja",
        "movimientos_caja",
    }.issubset(Egreso.metadata.tables)


def test_importes_usan_numeric_12_2_y_no_float():
    for model, names in (
        (Egreso, ("monto_pactado", "monto_solicitado", "monto_aprobado", "monto_pagado")),
        (AprobacionEgreso, ("monto_revisado",)),
        (PagoEgreso, ("monto",)),
        (MovimientoCaja, ("importe",)),
        (AperturaCaja, ("saldo",)),
    ):
        for name in names:
            column_type = model.__table__.c[name].type
            assert isinstance(column_type, Numeric)
            assert (column_type.precision, column_type.scale) == (12, 2)

    with pytest.raises(ValueError):
        CrearEgresoRequest(
            concepto_id=uuid4(),
            descripcion="Servicio",
            justificacion="Factura recibida",
            moneda="PEN",
            fecha_gasto="2026-11-25",
            monto_solicitado=10.25,
        )
    with pytest.raises(ValidationError):
        CrearEgresoRequest(
            concepto_id=uuid4(),
            descripcion="Servicio",
            justificacion="Factura recibida",
            moneda="PEN",
            fecha_gasto="2026-11-25",
            monto_solicitado="10.2",
        )
    with pytest.raises(ValidationError):
        CrearEgresoRequest(
            concepto_id=uuid4(),
            descripcion="Servicio",
            justificacion="Factura recibida",
            moneda="PEN",
            fecha_gasto="2026-11-25",
            monto_solicitado="0.00",
        )

    request = CrearEgresoRequest(
        concepto_id=uuid4(),
        descripcion="Servicio",
        justificacion="Factura recibida",
        moneda="PEN",
        fecha_gasto="2026-11-25",
        monto_solicitado="10.25",
    )
    assert request.monto_solicitado == Decimal("10.25")


def test_referencias_proveedor_contrato_son_uuid_nullable_y_sin_fk():
    for name in ("proveedor_id", "contrato_id"):
        column = Egreso.__table__.c[name]
        assert isinstance(column.type, UUID)
        assert column.nullable is True
        assert column.foreign_keys == set()

    request = CrearEgresoRequest(
        concepto_id=uuid4(),
        contrato_id=uuid4(),
        descripcion="Servicio",
        justificacion="Factura recibida",
        moneda="PEN",
        fecha_gasto="2026-11-25",
        monto_solicitado="10.25",
    )
    assert request.proveedor_id is None and request.contrato_id is not None


def test_egreso_relaciona_concepto_y_presupuesto_existentes():
    foreign_keys = {fk.target_fullname for fk in Egreso.__table__.c.concepto_id.foreign_keys}
    assert foreign_keys == {"conceptos_presupuestales.id"}
    assert {fk.target_fullname for fk in Egreso.__table__.c.presupuesto_id.foreign_keys} == {
        "presupuestos_mensuales.id"
    }
    assert any(
        constraint.name == "ck_egreso_presupuesto_item_par"
        for constraint in Egreso.__table__.constraints
    )


def test_documentos_y_historial_tienen_contexto_y_snapshots():
    assert "fk_documento_egreso_contexto" in {
        constraint.name for constraint in DocumentoFinanciero.__table__.constraints
    }
    assert {"estado_anterior_snapshot", "estado_posterior_snapshot"}.issubset(
        HistorialEgreso.__table__.columns.keys()
    )
    assert HistorialEgreso.__table__.c.actor_id.foreign_keys


def test_idempotencia_y_contexto_de_caja_tienen_constraints():
    assert "uq_pago_egreso_idempotency" in {
        constraint.name for constraint in PagoEgreso.__table__.constraints
    }
    assert "uq_apertura_caja_idempotency" in {
        constraint.name for constraint in AperturaCaja.__table__.constraints
    }
    assert "uq_reverso_pago_idempotency" in {
        constraint.name for constraint in ReversoPago.__table__.constraints
    }
    assert "fk_pago_cuenta_contexto" in {
        constraint.name for constraint in PagoEgreso.__table__.constraints
    }
    assert "uq_movimiento_caja_pago" in {
        constraint.name for constraint in MovimientoCaja.__table__.constraints
    }


def test_estados_persistidos_rechazan_valores_no_contemplados():
    estados = TypeAdapter(EstadoEgreso)
    assert estados.validate_python("BORRADOR") == "BORRADOR"
    with pytest.raises(ValidationError):
        estados.validate_python("PAGADO_Y_APROBADO")
    assert "ck_egreso_estado" in {c.name for c in Egreso.__table__.constraints}
    assert "ck_pago_egreso_estado" in {c.name for c in PagoEgreso.__table__.constraints}


def test_historial_y_documentos_son_append_only_en_migracion():
    script_path = Path("migrations/versions/20261202_0032_egresos_caja.py")
    source = script_path.read_text(encoding="utf-8")
    assert 'revision = "20261202_0032"' in source
    for table in (
        "documentos_financieros",
        "aprobaciones_egreso",
        "historial_egreso",
        "aperturas_caja",
        "reversos_pago_egreso",
        "movimientos_caja",
    ):
        assert f'"{table}"' in source
    assert "BEFORE UPDATE OR DELETE" in source


def test_configuracion_no_inventa_umbral_y_parciales_inician_deshabilitados():
    threshold = ConfiguracionAprobacionEgreso.__table__.c.umbral
    assert threshold.default is None
    assert threshold.server_default is None
    partials = ConfiguracionAprobacionEgreso.__table__.c.pagos_parciales_habilitados
    assert partials.default.arg is False
    assert str(partials.server_default.arg).lower() == "false"

    with pytest.raises(ValueError):
        ConfigurarAprobacionRequest(version_esperada=1)


def test_caja_no_tiene_saldo_inicial_automatico():
    assert not any(col.name in {"saldo", "saldo_inicial"} for col in CuentaCaja.__table__.columns)
    assert AperturaCaja.__table__.c.saldo.default is None
    assert AperturaCaja.__table__.c.saldo.server_default is None
    assert MovimientoCaja.__table__.c.importe.default is None

    apertura = RegistrarAperturaCajaRequest(
        cuenta_referencia="OPERATIVA-01",
        moneda="PEN",
        saldo="0.00",
        fecha_corte="2026-11-25",
        referencia="Conciliación de corte firmada",
        documento_id=uuid4(),
    )
    assert apertura.saldo == Decimal("0.00")


def test_aprobacion_requiere_motivo_al_rechazar():
    with pytest.raises(ValueError):
        RegistrarAprobacionRequest(decision="RECHAZAR", version_esperada=1)


def test_migracion_de_egresos_se_aplica_despues_de_proveedores():
    config = Config("alembic.ini")
    scripts = ScriptDirectory.from_config(config)
    revision = scripts.get_revision("20261202_0032")
    assert revision.down_revision == "20261201_0031"
