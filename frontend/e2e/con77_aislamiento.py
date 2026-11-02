"""Regresión Chromium de contexto de Junta. API interceptada; no certifica SQL.

Instalar: pip install playwright; python -m playwright install chromium
Iniciar Next.js local y ejecutar: python frontend/e2e/con77_aislamiento.py
"""

import argparse
import asyncio
import json

from playwright.async_api import async_playwright, expect

A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
P = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
PERFIL = {
    "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    "email": "superadmin@con77.test",
    "nombre": "Prueba",
    "apellido": "CON77",
    "rol": "SUPERADMIN",
    "condominio_id": None,
    "departamentos": [],
}


async def verificar(url):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(15000)
        pendientes = []
        aprobaciones = []
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))
        await page.add_init_script(
            "localStorage.setItem('condo_token', 'con77-browser');"
            f"localStorage.setItem('condo_user', JSON.stringify({json.dumps(PERFIL)}));"
            f"localStorage.setItem('condo_active_id', '{A}');"
        )

        async def responder(route):
            request = route.request
            path = request.url.split("/api/v1", 1)[1].split("?", 1)[0]
            if request.method == "OPTIONS":
                await route.fulfill(status=204)
                return
            assert request.headers.get("authorization") == "Bearer con77-browser"
            if path == "/auth/me":
                data = PERFIL
            elif path == "/condominios":
                data = [
                    {
                        "id": cid,
                        "nombre": nombre,
                        "direccion": nombre,
                        "moneda": "PEN",
                        "regla_mora_tipo": "MONTO_FIJO",
                        "monto_mora_fijo": "0.00",
                        "monto_mora_diario": None,
                        "tasa_mora_porcentaje": None,
                        "dia_vencimiento": 20,
                        "dias_gracia": 0,
                        "activo": True,
                        "politica_version": 1,
                    }
                    for cid, nombre in ((A, "Condominio A"), (B, "Condominio B"))
                ]
            elif path == "/notificaciones/comunicado-masivo":
                pendientes.append(route)
                return  # La prueba decide cuándo llega la respuesta tardía.
            elif path == f"/presupuestos/{P}/aprobar":
                aprobaciones.append(route)
                return
            elif "/presupuestos/" in path and path.startswith("/condominios/"):
                if not path.startswith(f"/condominios/{A}/"):
                    await route.fulfill(
                        status=404, json={"error_code": "PRESUPUESTO_NO_ENCONTRADO"}
                    )
                    return
                periodo = path.rsplit("/", 1)[1]
                data = {
                    "id": P,
                    "condominio_id": A,
                    "periodo": periodo,
                    "moneda": "PEN",
                    "monto_total": "100.00",
                    "fecha_vencimiento": periodo + "-20",
                    "estado": "BORRADOR",
                    "version": 1,
                    "items": None,
                    "aprobado_por": None,
                    "aprobado_en": None,
                }
            else:
                data = []
            await route.fulfill(json=data)

        await page.route("**/api/v1/**", responder)
        await page.goto(url + "/junta")
        print("Chromium: portal cargado", flush=True)
        nav = page.get_by_role("navigation", name="Secciones de Junta")

        async def comunicados():
            await nav.get_by_role("button", name="Comunicados", exact=True).click()

        async def cambiar(cid):
            await nav.get_by_role("button", name="Configuración", exact=True).click()
            await page.get_by_label("Condominio activo", exact=True).select_option(cid)
            await expect(page.get_by_label("Condominio activo", exact=True)).to_have_value(cid)
            await comunicados()

        await comunicados()
        print("Chromium: comprobando borradores", flush=True)
        await page.get_by_label("Título", exact=False).fill("Borrador privado A")
        await page.get_by_label("Mensaje", exact=False).fill("Contenido exclusivo del condominio A")
        await cambiar(B)
        await expect(page.get_by_label("Título", exact=False)).to_have_value("")
        await expect(page.get_by_label("Mensaje", exact=False)).to_have_value("")

        # Iniciar en B, cerrar el modal mientras responde y pasar a A.
        await page.get_by_label("Título", exact=False).fill("Mensaje B")
        await page.get_by_label("Mensaje", exact=False).fill("Contenido exclusivo del condominio B")
        await page.get_by_role("button", name="Enviar comunicado", exact=True).click()
        await (
            page.get_by_role("dialog")
            .get_by_role("button", name="Enviar comunicado", exact=True)
            .click()
        )
        await expect(
            page.get_by_role("dialog").get_by_role("button", name="Cerrar", exact=True)
        ).to_be_visible()
        await page.get_by_role("dialog").get_by_role("button", name="Cerrar", exact=True).click()
        await cambiar(A)
        await page.get_by_label("Título", exact=False).fill("Nuevo borrador A")
        await page.get_by_label("Mensaje", exact=False).fill("Este borrador debe conservarse")
        await cambiar(B)
        await page.get_by_label("Título", exact=False).fill("Segunda visita a B")
        await page.get_by_label("Mensaje", exact=False).fill("Borrador nuevo de B")
        assert len(pendientes) == 1
        assert pendientes[0].request.post_data_json["condominio_id"] == B
        async with page.expect_response("**/notificaciones/comunicado-masivo"):
            await pendientes[0].fulfill(
                status=202, json={"generadas": 999, "estado_general": "EN_COLA"}
            )
        await page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        await expect(page.get_by_label("Título", exact=False)).to_have_value("Segunda visita a B")
        await expect(page.get_by_label("Mensaje", exact=False)).to_have_value("Borrador nuevo de B")
        await expect(
            page.get_by_text("Comunicado en cola para 999 destinatarios.", exact=False)
        ).to_have_count(0)

        # Cada cambio también descarta los borradores de la visita anterior.
        await cambiar(A)
        await expect(page.get_by_label("Título", exact=False)).to_have_value("")
        await expect(page.get_by_label("Mensaje", exact=False)).to_have_value("")

        # Una aprobación que termina después de salir de A no habilita emisión en B.
        await nav.get_by_role("button", name="Presupuesto", exact=True).click()
        await expect(page.get_by_text("Borrador cargado.", exact=True)).to_be_visible()
        await page.get_by_role("button", name="Aprobar presupuesto", exact=True).click()
        await (
            page.get_by_role("dialog")
            .get_by_role("button", name="Aprobar presupuesto", exact=True)
            .click()
        )
        await page.get_by_role("dialog").get_by_role("button", name="Cerrar", exact=True).click()
        await cambiar(B)
        assert len(aprobaciones) == 1
        async with page.expect_response(f"**/presupuestos/{P}/aprobar*"):
            await aprobaciones[0].fulfill(
                json={
                    "id": P,
                    "condominio_id": A,
                    "periodo": "2026-11",
                    "moneda": "PEN",
                    "monto_total": "100.00",
                    "fecha_vencimiento": "2026-11-20",
                    "estado": "APROBADO",
                    "version": 1,
                    "items": None,
                    "aprobado_por": PERFIL["id"],
                    "aprobado_en": "2026-11-01T20:00:00Z",
                }
            )
        await page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        await nav.get_by_role("button", name="Distribución y emisión", exact=True).click()
        await expect(page.get_by_role("button", name="Emitir cuotas", exact=True)).to_be_disabled()
        assert not errores, errores
        print("CON-77 Chromium: borradores aislados, cambio de contexto y respuesta tardía: OK")
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:3077")
    asyncio.run(verificar(parser.parse_args().url.rstrip("/")))
