import io
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from PIL import Image
from pypdf import PdfWriter

from src.core.errors import APIError
from src.modules.pagos.contabilidad import plan_imputacion, saldo_en_mora
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
    assert exc.value.status_code == 422
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
