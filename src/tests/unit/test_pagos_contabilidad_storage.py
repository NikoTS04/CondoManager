import io
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from PIL import Image
from pypdf import PdfWriter

from src.core.errors import APIError
from src.modules.pagos.contabilidad import (
    plan_imputacion,
    saldo_en_mora,
    validar_conservacion_pago,
)
from src.modules.pagos.storage import MAX_BYTES, VoucherStorage


def cuota(**extra):
    return SimpleNamespace(
        **{
            "id": uuid4(),
            "periodo": "2026-10",
            "estado": "PENDIENTE",
            "monto_mora": Decimal("0.00"),
            "monto_extraordinario": Decimal("0.00"),
            "monto_total_exigible": Decimal("100.00"),
            "monto_pagado": Decimal("0.00"),
            "fecha_vencimiento": date(2026, 10, 20),
            "fecha_emision": date(2026, 10, 1),
            "dias_gracia_aplicados": None,
            **extra,
        }
    )


@pytest.mark.parametrize("desplazamiento,esperado", [(0, "0.00"), (2, "0.00"), (3, "100.00")])
def test_frontera_gracia(desplazamiento, esperado):
    c = cuota()
    assert saldo_en_mora([c], 2, c.fecha_vencimiento + timedelta(days=desplazamiento)) == Decimal(
        esperado
    )


def test_prelacion_por_componentes_no_solo_por_fecha():
    vieja = cuota(fecha_vencimiento=date(2026, 8, 20), periodo="2026-08")
    nueva = cuota(
        fecha_vencimiento=date(2026, 9, 20), periodo="2026-09", monto_mora=Decimal("20.00")
    )
    plan = plan_imputacion([vieja, nueva], Decimal("20.00"), date(2026, 10, 25))
    assert plan["aplicaciones"] == {nueva.id: Decimal("20.00")}


def test_pagos_previos_y_futuras_no_se_cuentan_dos_veces():
    parcial = cuota(monto_mora=Decimal("20.00"), monto_pagado=Decimal("15.00"))
    futura = cuota(periodo="2026-12", fecha_vencimiento=date(2026, 12, 20))
    plan = plan_imputacion([parcial, futura], Decimal("100.00"), date(2026, 10, 25))
    assert plan["aplicaciones"] == {parcial.id: Decimal("85.00")}
    assert plan["remanente"] == Decimal("15.00")


@pytest.mark.parametrize("monto", ["0.01", "15.00", "65.00", "195.00", "235.00", "250.00"])
def test_prelacion_completa_y_conservacion_independientes_del_orden(monto):
    a = cuota(
        id=UUID(int=1),
        periodo="2026-08",
        fecha_emision=date(2026, 8, 1),
        fecha_vencimiento=date(2026, 8, 10),
        monto_mora=Decimal("5.00"),
        monto_extraordinario=Decimal("20.00"),
        monto_total_exigible=Decimal("95.00"),
    )
    b = cuota(
        id=UUID(int=2),
        periodo="2026-09",
        fecha_emision=date(2026, 9, 1),
        fecha_vencimiento=date(2026, 9, 10),
        monto_mora=Decimal("10.00"),
        monto_extraordinario=Decimal("30.00"),
        monto_total_exigible=Decimal("100.00"),
    )
    actual = cuota(id=UUID(int=3), monto_total_exigible=Decimal("40.00"))
    importe = Decimal(monto)
    plan = plan_imputacion([actual, b, a], importe, date(2026, 10, 5))
    assert plan == plan_imputacion([a, b, actual], importe, date(2026, 10, 5))
    assert sum(plan["aplicaciones"].values(), Decimal("0.00")) + plan["remanente"] == importe
    restante = importe
    esperados = {a.id: [Decimal(0)] * 3, b.id: [Decimal(0)] * 3, actual.id: [Decimal(0)] * 3}
    for cid, tipo, pendiente in [
        (a.id, 0, 5),
        (b.id, 0, 10),
        (a.id, 1, 20),
        (b.id, 1, 30),
        (a.id, 2, 70),
        (b.id, 2, 60),
        (actual.id, 2, 40),
    ]:
        aplicado = min(restante, Decimal(pendiente))
        esperados[cid][tipo] = aplicado
        restante -= aplicado
    assert plan["componentes"] == {cid: v for cid, v in esperados.items() if any(v)}
    assert plan["remanente"] == restante


def test_no_imputa_cuota_emitida_despues_de_fecha_bancaria():
    posterior = cuota(fecha_emision=date(2026, 10, 15))
    plan = plan_imputacion([posterior], Decimal("100.00"), date(2026, 10, 10))
    assert plan == {"aplicaciones": {}, "componentes": {}, "remanente": Decimal("100.00")}


@pytest.mark.parametrize(
    "aplicado,credito",
    [("101.00", "0.00"), ("99.00", "0.00"), ("-1.00", "101.00"), ("NaN", "0.00")],
)
def test_conservacion_rechaza_planes_inconsistentes(aplicado, credito):
    with pytest.raises(APIError) as exc:
        validar_conservacion_pago(Decimal("100.00"), Decimal(aplicado), Decimal(credito))
    assert exc.value.error_code == "IMPUTACION_PAGO_INCONSISTENTE"


@pytest.mark.parametrize("formato,extension", [("PNG", ".png"), ("JPEG", ".jpg"), ("PDF", ".pdf")])
def test_contenido_real_nombre_generado_y_recuperacion(tmp_path, formato, extension):
    buffer = io.BytesIO()
    if formato == "PDF":
        pdf = PdfWriter()
        pdf.add_blank_page(width=100, height=100)
        pdf.write(buffer)
    else:
        Image.new("RGB", (2, 2), "white").save(buffer, format=formato)
    storage = VoucherStorage(tmp_path)
    nombre, _ = storage.guardar(buffer.getvalue())
    assert nombre.endswith(extension) and "/" not in nombre and "\\" not in nombre
    assert storage.ruta(nombre).read_bytes() == buffer.getvalue()
    storage.eliminar(nombre)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize(
    "contenido", [b"", b"<html>no es imagen</html>", b"%PDF-1.7\n%%EOF", b"\x89PNG\r\n\x1a\n"]
)
def test_archivo_corrupto_no_se_guarda(tmp_path, contenido):
    with pytest.raises(APIError) as exc:
        VoucherStorage(tmp_path).guardar(contenido)
    assert exc.value.status_code == (415 if contenido.startswith(b"<html>") else 422)
    assert not list(tmp_path.iterdir())


def test_limite_y_traversal(tmp_path):
    storage = VoucherStorage(tmp_path)
    with pytest.raises(APIError) as exc:
        storage.guardar(b"x" * (MAX_BYTES + 1))
    assert exc.value.status_code == 413
    for nombre in (
        "../secreto",
        "C:\\Windows\\archivo.jpg",
        "https://externo/voucher.jpg",
        "blob:algo",
    ):
        with pytest.raises(APIError):
            storage.ruta(nombre)


def test_worker_independiente_registra_sus_claves_foraneas():
    # Importar app en conftest ocultaba los modelos faltantes del proceso de relay.
    programa = (
        "from src.modules.pagos.worker import ArchivoVoucher, EventoPagoOutbox; "
        "assert all(fk.column is not None for t in (ArchivoVoucher, EventoPagoOutbox) "
        "for fk in t.__table__.foreign_keys)"
    )
    subprocess.run([sys.executable, "-c", programa], check=True, capture_output=True, text=True)
