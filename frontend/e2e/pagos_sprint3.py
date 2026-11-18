"""Bordes de UI CON-25–28 con API interceptada; no sustituye evidencia SQL real."""

import argparse
import asyncio
from urllib.parse import parse_qs, urlsplit

from con77_aislamiento import PERFIL, A, B
from playwright.async_api import async_playwright, expect

PAGO = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
UNIDAD = "ffffffff-ffff-4fff-8fff-ffffffffffff"
RECIBO = {
    "comprobante_id": PAGO,
    "estado_final": "APROBADO",
    "monto_imputado": "100.00",
    "nuevo_saldo_departamento": "0.00",
    "saldo_a_favor_generado": "20.00",
    "departamento_habilitado_reservas": True,
    "motivo_rechazo": None,
}


async def verificar(url):
    import json

    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        await page.add_init_script(
            "localStorage.setItem('condo_token', 'con77-browser');"
            f"localStorage.setItem('condo_user', JSON.stringify({json.dumps(PERFIL)}));"
            f"localStorage.setItem('condo_active_id', '{A}');"
        )
        estado = "EN_REVISION"
        posts = []
        lecturas = []
        modo = "conflicto"

        async def responder(route):
            nonlocal estado
            request = route.request
            parsed = urlsplit(request.url)
            path = parsed.path.split("/api/v1", 1)[1]
            query = parse_qs(parsed.query)
            if request.method == "OPTIONS":
                await route.fulfill(status=204)
                return
            if path.endswith("/conciliar"):
                posts.append(request.post_data_json)
                if modo == "conflicto":
                    await route.fulfill(
                        status=409,
                        json={
                            "error_code": "FONDOS_MORAS_COMPROMETIDOS",
                            "mensaje": "La corrección afecta fondos reservados.",
                        },
                    )
                else:
                    estado = "APROBADO"  # Commit confirmado, pero respuesta perdida.
                    await route.abort("failed")
                return
            if path.endswith("/resultado"):
                if modo == "lectura_tardia":
                    lecturas.append(route)
                    return
                if estado == "APROBADO":
                    await route.fulfill(json=RECIBO)
                else:
                    await route.fulfill(status=404, json={"error_code": "RESULTADO_NO_DISPONIBLE"})
                return
            if path == "/auth/me":
                data = PERFIL
            elif path == "/condominios":
                data = [
                    {
                        "id": cid,
                        "nombre": nombre,
                        "direccion": "Prueba",
                        "moneda": "PEN",
                        "activo": True,
                        "regla_mora_tipo": "MONTO_FIJO",
                        "monto_mora_fijo": "0.00",
                        "monto_mora_diario": None,
                        "tasa_mora_porcentaje": None,
                        "dia_vencimiento": 10,
                        "dias_gracia": 0,
                        "politica_version": 1,
                    }
                    for cid, nombre in ((A, "Condominio A"), (B, "Condominio B"))
                ]
            elif path == "/pagos/comprobantes":
                data = (
                    [
                        {
                            "id": PAGO,
                            "departamento_id": UNIDAD,
                            "banco": "BCP",
                            "numero_operacion": "S3-UI",
                            "fecha_operacion": "2026-10-10",
                            "monto": "120.00",
                            "estado": estado,
                            "idempotency_hash": "a" * 64,
                            "url_voucher": f"/api/v1/pagos/{PAGO}/voucher",
                            "motivo_rechazo": None,
                        }
                    ]
                    if query.get("condominio_id") == [A]
                    else []
                )
            else:
                data = []
            await route.fulfill(json=data)

        await page.route("**/api/v1/**", responder)
        await page.goto(url + "/junta")
        nav = page.get_by_role("navigation", name="Secciones de Junta")
        await nav.get_by_role("button", name="Conciliación", exact=False).click()

        async def aprobar():
            await (
                page.locator("tr")
                .filter(has_text="S3-UI")
                .get_by_role("button", name="Aprobar", exact=True)
                .click()
            )
            await (
                page.get_by_role("dialog")
                .get_by_role("button", name="Aprobar comprobante", exact=True)
                .click()
            )
            await expect(page.get_by_role("dialog")).not_to_be_visible()

        await aprobar()
        await expect(
            page.get_by_role("alert").filter(has_text="La corrección afecta fondos reservados.")
        ).to_be_visible()
        await expect(
            page.get_by_text("Código: FONDOS_MORAS_COMPROMETIDOS", exact=True)
        ).to_be_visible()
        assert len(posts) == 1
        await page.get_by_role("button", name="Cerrar resultado", exact=True).click()

        modo = "respuesta_perdida"
        await aprobar()
        await expect(
            page.get_by_text("No se pudo confirmar la respuesta.", exact=False)
        ).to_be_visible()
        await expect(page.get_by_text("Crédito de este pago", exact=True)).to_be_visible()
        assert len(posts) == 2  # El GET de recuperación no produjo otro POST.

        modo = "lectura_tardia"
        await page.reload()
        await nav.get_by_role("button", name="Conciliación", exact=False).click()
        await page.get_by_role("button", name="Ver resultado", exact=True).click()
        await expect(
            page.get_by_text("Consultando resultado del pago…", exact=True)
        ).to_be_attached()
        await nav.get_by_role("button", name="Configuración", exact=True).click()
        await page.get_by_label("Condominio activo", exact=True).select_option(B)
        await nav.get_by_role("button", name="Conciliación", exact=False).click()
        assert len(lecturas) == 1
        await lecturas[0].fulfill(json=RECIBO)
        await expect(page.get_by_text("No hay comprobantes", exact=True)).to_be_visible()
        await expect(page.get_by_text("Resultado de la revisión", exact=True)).to_have_count(0)
        assert len(posts) == 2
        await browser.close()
        print(
            "CON-25–28 UI: error financiero, respuesta incierta y recibo tardío de otro contexto: OK"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:3079")
    asyncio.run(verificar(parser.parse_args().url.rstrip("/")))
