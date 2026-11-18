"""Chromium → API HTTP real → PostgreSQL efímero: evidencia CON-25–28.

Requiere frontend local compilado con NEXT_PUBLIC_API_URL=http://127.0.0.1:8045/api/v1
y NEXT_PUBLIC_DEMO_MODE=false. Arranca solo una API de pruebas en 127.0.0.1:8045,
crea un esquema propio y lo elimina al terminar. No intercepta respuestas de API.
El correo se verifica como EN_COLA, no como entrega de CON-78.
"""

import argparse
import asyncio
import hashlib
import json
import os
import subprocess
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@contextmanager
def servidor(app):
    import uvicorn

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8045, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        for _ in range(150):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError(
                    "La API de pruebas no pudo arrancar en el puerto exclusivo 8045."
                )
            time.sleep(0.1)
        else:
            raise RuntimeError("La API de pruebas no estuvo lista a tiempo.")
        yield
    finally:
        server.should_exit = True
        thread.join(timeout=15)


async def preparar(base):
    from datetime import date
    from decimal import Decimal

    from src.modules.condominios.models import Departamento
    from src.modules.cuotas.models import CuotaMantenimiento
    from src.tests.pagos_db import did
    from src.tests.pagos_sprint3 import preparar as preparar_parcial

    await preparar_parcial(base)
    async with base.sessions() as db, db.begin():
        (await db.get(Departamento, did("402"))).saldo_a_favor = Decimal("0.00")
        db.add(
            CuotaMantenimiento(
                id=uuid4(),
                departamento_id=did("402"),
                periodo="2026-10",
                monto_ordinario=Decimal("100.00"),
                monto_total_exigible=Decimal("100.00"),
                monto_pagado=Decimal("0.00"),
                fecha_emision=date(2026, 10, 1),
                fecha_vencimiento=date(2026, 10, 10),
                dias_gracia_aplicados=0,
                estado="PENDIENTE",
            )
        )


async def resumen_sql(base):
    from sqlalchemy import select

    from src.core.models_audit import AuditoriaLogORM
    from src.modules.condominios.models import Departamento
    from src.modules.cuotas.models import CuotaMantenimiento
    from src.modules.notificaciones.consumo import consumir
    from src.modules.notificaciones.models import Notificacion
    from src.modules.pagos.models import ImputacionPago
    from src.modules.pagos.models_persistencia import EventoPagoOutbox, RevisionPago
    from src.tests.pagos_db import did

    async with base.sessions() as db:
        eventos = list(await db.scalars(select(EventoPagoOutbox)))
    for e in eventos:
        await consumir(base.sessions, e.payload)
        assert await consumir(base.sessions, e.payload) == 0
    async with base.sessions() as db:
        cuotas = list(await db.scalars(select(CuotaMantenimiento)))
        unidades = {str(d.id): d for d in await db.scalars(select(Departamento))}
        revisiones = list(
            await db.scalars(select(RevisionPago).order_by(RevisionPago.creado_en, RevisionPago.id))
        )
        aplicaciones = list(await db.scalars(select(ImputacionPago)))
        logs = list(
            await db.scalars(
                select(AuditoriaLogORM).order_by(AuditoriaLogORM.timestamp, AuditoriaLogORM.id)
            )
        )
        avisos = list(await db.scalars(select(Notificacion)))
        assert all(b.hash_previo == a.hash_actual for a, b in zip(logs, logs[1:]))
        assert len(revisiones) == 5 and len(aplicaciones) == 3
        assert len(eventos) == 10 and len(avisos) == 10
        assert all(a.estado == "EN_COLA" for a in avisos)
        return {
            "unidades": [
                {
                    "id": str(c.departamento_id),
                    "cuota_id": str(c.id),
                    "estado": c.estado,
                    "exigible": str(c.monto_total_exigible),
                    "pagado": str(c.monto_pagado),
                    "credito": str(unidades[str(c.departamento_id)].saldo_a_favor),
                }
                for c in cuotas
                if c.departamento_id in {did("102"), did("402")}
            ],
            "revisiones": [r.resultado for r in revisiones],
            "imputaciones": [
                {
                    "comprobante_id": str(i.comprobante_id),
                    "cuota_id": str(i.cuota_id),
                    "monto": str(i.monto_aplicado),
                }
                for i in aplicaciones
            ],
            "auditorias": len(logs),
            "cadena_hashes_valida": True,
            "eventos": len(eventos),
            "avisos_en_cola": len(avisos),
            "correo_real": "PENDIENTE_CON_78",
        }


def navegador(url, salida):
    from playwright.sync_api import expect, sync_playwright

    from src.tests.integration.test_pagos_db import imagen

    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        errores = []

        def entrar(cuenta, password):
            page = browser.new_page(viewport={"width": 1440, "height": 1000})
            page.on("pageerror", lambda e: errores.append(str(e)))
            page.goto(url + "/login")
            page.get_by_label("Correo electrónico").fill(cuenta + "@villabonita3.pe")
            page.get_by_label("Contraseña").fill(password)
            page.get_by_role("button", name="Iniciar sesión", exact=True).click()
            page.wait_for_url("**/junta*" if cuenta == "admin" else "**/residente*")
            return page

        residente = entrar("residente102", "Residente123!")
        admin = entrar("admin", "Admin123!")
        exacto = entrar("moroso402", "Moroso123!")

        def reportar(page, monto):
            page.get_by_role("tab", name="Pagos", exact=True).click()
            operacion = "S3-" + uuid4().hex[:12]
            page.get_by_label("Número de Operación Bancaria").fill(operacion)
            page.get_by_label("Monto Pagado").fill(monto)
            page.get_by_label("Fecha de Operación", exact=False).fill("2026-10-10")
            page.locator('input[type="file"]').first.set_input_files(
                {
                    "name": "prueba.png",
                    "mimeType": "image/png",
                    "buffer": imagen(),
                }
            )
            page.get_by_role("button", name="Reportar Pago", exact=True).click()
            with page.expect_response("**/pagos/reportar") as response:
                page.get_by_role("button", name="Confirmar y enviar", exact=True).click()
            assert response.value.status == 202, response.value.text()
            return operacion, response.value.json()["comprobante_id"]

        def decidir(op, decision="Aprobar", motivo=None):
            admin.reload()
            admin.get_by_role("navigation", name="Secciones de Junta").get_by_role(
                "button", name="Conciliación", exact=False
            ).click()
            fila = admin.locator("tr").filter(has_text=op)
            fila.get_by_role("button", name=decision, exact=True).click()
            dialog = admin.get_by_role("dialog")
            if motivo:
                dialog.get_by_label("Motivo de la observación o rechazo").fill(motivo)
            dialog.get_by_label("Notas internas (opcional)", exact=True).fill(
                "Evidencia sintética privada"
            )
            with admin.expect_response("**/conciliar") as response:
                dialog.get_by_role("button", name=decision + " comprobante", exact=True).click()
            assert response.value.status == 200, response.value.text()
            expect(admin.get_by_text("Resultado de la revisión", exact=True)).to_be_visible()
            expect(dialog).not_to_be_visible()
            expect(admin.locator("tr").filter(has_text=op)).to_be_visible()
            return response.value.json()

        op, pid = reportar(exacto, "100.00")
        r = decidir(op)
        assert r["monto_imputado"] == "100.00" and r["nuevo_saldo_departamento"] == "0.00"
        admin.screenshot(path=str(salida / "CON-25-aprobacion.png"), full_page=True)

        op, _ = reportar(residente, "40.00")
        r = decidir(op)
        assert (
            r["nuevo_saldo_departamento"] == "60.00" and not r["departamento_habilitado_reservas"]
        )
        admin.screenshot(path=str(salida / "CON-27-parcial.png"), full_page=True)

        op, _ = reportar(residente, "80.00")
        r = decidir(op)
        assert r["saldo_a_favor_generado"] == "20.00" and r["nuevo_saldo_departamento"] == "0.00"
        admin.set_viewport_size({"width": 390, "height": 844})
        admin.screenshot(path=str(salida / "CON-28-excedente-movil.png"), full_page=True)
        assert admin.evaluate("document.documentElement.scrollWidth <= innerWidth")
        admin.set_viewport_size({"width": 1440, "height": 1000})

        op, observado = reportar(residente, "50.00")
        decidir(op, "Observar", "Adjunta una imagen legible para verificar la operación.")
        admin.screenshot(path=str(salida / "CON-26-observado.png"), full_page=True)
        residente.reload()
        residente.get_by_role("tab", name="Pagos", exact=True).click()
        residente.get_by_role("button", name="Subsanar voucher", exact=True).click()
        residente.get_by_label("Nuevo voucher para subsanar").set_input_files(
            {
                "name": "corregido.png",
                "mimeType": "image/png",
                "buffer": imagen(),
            }
        )
        with residente.expect_response(f"**/pagos/{observado}/voucher") as response:
            residente.get_by_role("button", name="Enviar subsanación", exact=True).click()
        assert response.value.status == 202
        decidir(op, "Rechazar", "La operación no figura acreditada. Contacta con administración.")
        admin.screenshot(path=str(salida / "CON-26-rechazado.png"), full_page=True)

        # Otra sesión y recarga recuperan el mismo recibo, sin nuevo POST.
        exacto.reload()
        exacto.get_by_role("tab", name="Pagos", exact=True).click()
        with exacto.expect_response(f"**/pagos/{pid}/resultado") as response:
            exacto.get_by_role("button", name="Ver resultado", exact=True).click()
        assert response.value.json()["monto_imputado"] == "100.00"
        expect(exacto.get_by_text("Resultado de la revisión", exact=True)).to_be_visible()
        exacto.screenshot(path=str(salida / "CON-25-recibo-residente.png"), full_page=True)
        assert "Evidencia sintética privada" not in exacto.locator("body").inner_text()
        assert not errores, errores
        browser.close()
        return pid


def main():
    from scripts.verificar_pagos_sprint3 import entorno_pruebas

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-url", default="http://127.0.0.1:3079")
    parser.add_argument(
        "--database-url",
        default="postgresql+asyncpg://sprint3:sprint3_local_test@127.0.0.1:55425/sprint3_test",
    )
    parser.add_argument("--confirmar-entorno-pruebas", action="store_true", required=True)
    args = parser.parse_args()
    parsed = urlsplit(args.frontend_url)
    if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
        parser.error("El frontend de evidencia debe ser local.")
    try:
        os.environ.update(entorno_pruebas(args.database_url))
    except ValueError as exc:
        parser.error(str(exc))
    # Configurar entorno seguro ANTES de importar aplicación, engine o fixtures.
    import httpx
    import pytest

    from src.core.database import get_db_session
    from src.main import app
    from src.tests.pagos_sprint3 import fijar_reloj
    from src.tests.usuarios_db import borrar_base, crear_base

    salida = ROOT / "tmp/sprint3/evidencias" / uuid4().hex[:8]
    salida.mkdir(parents=True)
    base = asyncio.run(crear_base(args.database_url))
    try:
        with pytest.MonkeyPatch.context() as monkeypatch:
            fijar_reloj(monkeypatch, salida)
            asyncio.run(preparar(base))

            async def session():
                async with base.sessions() as db:
                    try:
                        yield db
                        await db.commit()
                    except Exception:
                        await db.rollback()
                        raise

            monkeypatch.setitem(app.dependency_overrides, get_db_session, session)
            with servidor(app):
                pid = navegador(args.frontend_url.rstrip("/"), salida)
            asyncio.run(base.engine.dispose())
            with servidor(app), httpx.Client(base_url="http://127.0.0.1:8045") as client:
                login = client.post(
                    "/api/v1/auth/login",
                    json={
                        "email": "moroso402@villabonita3.pe",
                        "password": "Moroso123!",
                    },
                )
                assert login.status_code == 200
                r = client.get(
                    f"/api/v1/pagos/{UUID(pid)}/resultado",
                    headers={
                        "Authorization": "Bearer " + login.json()["access_token"],
                    },
                )
                assert r.status_code == 200 and r.json()["monto_imputado"] == "100.00"
            resumen = asyncio.run(resumen_sql(base))
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            fuentes = [
                *ROOT.glob("src/modules/pagos/*.py"),
                *ROOT.glob("frontend/src/components/domain/ResultadoPago.tsx"),
                *ROOT.glob("frontend/src/features/junta/*Conciliacion*.tsx"),
                ROOT / "frontend/src/features/junta/JuntaPortal.tsx",
                ROOT / "frontend/src/features/residente/ComprobantesList.tsx",
                ROOT / "frontend/src/lib/api.ts",
            ]
            resumen.update(
                api_reiniciada=True,
                navegador="Chromium con API HTTP y PostgreSQL reales",
                base_git=head + " + cambios locales sin commit",
                sha256_fuentes={
                    str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(fuentes)
                },
            )
            (salida / "evidencia-sql.json").write_text(
                json.dumps(resumen, indent=2), encoding="utf-8"
            )
            print(json.dumps({"resultado": "OK", "evidencias": str(salida)}, ensure_ascii=False))
    finally:
        asyncio.run(borrar_base(base))


if __name__ == "__main__":
    main()
