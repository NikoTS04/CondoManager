"""CON-14: Chromium con API interceptada; SQL se verifica en integración y BDD."""

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from playwright.async_api import async_playwright, expect

A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
CID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
USER = {
    "id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    "email": "residente@con14.test",
    "nombre": "Residente",
    "apellido": "CON14",
    "rol": "RESIDENTE",
    "condominio_id": CID,
    "departamentos": [
        {"departamento_id": uid, "numero": numero, "tipo_relacion": "INQUILINO", "es_activo": True}
        for uid, numero in ((A, "102"), (B, "504"))
    ],
}


def cuenta(uid, query):
    desde, hasta = query["desde"][0], query["hasta"][0]
    offset = int(query.get("offset", ["0"])[0])
    rows = (
        [
            {
                "id": f"mov-{i}",
                "fecha": desde,
                "registrado_en": desde + "T12:00:00Z",
                "fecha_operacion": None,
                "tipo": "EMISION_CUOTA"
                if i == 0
                else "PAGO_APROBADO"
                if i == 1
                else "DISTRIBUCION_PAGO",
                "descripcion": "Cargo privado de unidad A"
                if i == 0
                else "Pago aprobado"
                if i == 1
                else "Aplicación de pago",
                "importe": "100.00" if i == 0 else "40.00",
                "cargo": "100.00" if i == 0 else "0.00",
                "abono": "40.00" if i == 1 else "0.00",
                "saldo": "100.00" if i == 0 else "60.00",
                "cuota_id": A,
                "comprobante_id": None,
                "origen_id": A,
                "periodo_cuota": desde[:7],
            }
            for i in range(51)
        ]
        if uid == A
        else []
    )
    return {
        "departamento_id": uid,
        "condominio_id": CID,
        "moneda": "PEN",
        "desde": desde,
        "hasta": hasta,
        "generado_en": "2026-11-02T12:00:00Z",
        "historial_desde": desde,
        "base_historica_sin_fecha": False,
        "credito_inicial_sin_desglose": "0.00",
        "abonos_historicos_sin_desglose": "0.00",
        "saldo_base_historico": "0.00",
        "saldo_inicial": "0.00",
        "cargos_periodo": "100.00" if rows else "0.00",
        "abonos_periodo": "40.00" if rows else "0.00",
        "saldo_final": "60.00" if rows else "0.00",
        "deuda_actual": "60.00" if rows else "0.00",
        "deuda_vencida_actual": "60.00" if rows else "0.00",
        "saldo_a_favor_actual": "0.00",
        "saldo_neto_actual": "60.00" if rows else "0.00",
        "total_movimientos": len(rows),
        "limite": 50,
        "offset": offset,
        "movimientos": rows[offset : offset + 50],
        "pagos_en_revision": [
            {
                "id": A,
                "fecha_reporte": desde,
                "fecha_operacion": desde,
                "banco": "BCP",
                "numero_operacion": "PENDIENTE-A",
                "monto": "999.99",
            }
        ]
        if rows
        else [],
    }


async def verificar(url):
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 1000})
        page.set_default_timeout(15000)
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))
        await page.add_init_script(
            f"localStorage.setItem('condo_token','con14-browser'); localStorage.setItem('condo_user',JSON.stringify({json.dumps(USER)}));"
        )
        fallar_b = True

        async def responder(route):
            nonlocal fallar_b
            req = route.request
            parsed = urlparse(req.url)
            path = parsed.path.split("/api/v1", 1)[1]
            if req.method == "OPTIONS":
                await route.fulfill(status=204)
                return
            assert req.headers.get("authorization") == "Bearer con14-browser"
            if path == "/auth/me":
                data = USER
            elif path == "/cuotas/departamentos":
                data = [
                    {
                        "id": uid,
                        "numero": num,
                        "piso": 1,
                        "coeficiente": "50.0000",
                        "condominio_id": CID,
                        "edificio_nombre": "Torre de prueba",
                        "activo": True,
                        "saldo_a_favor": "0.00",
                        "deuda_vencida": "60.00" if uid == A else "0.00",
                        "estado_financiero": "EN_MORA" if uid == A else "AL_DIA",
                    }
                    for uid, num in ((A, "102"), (B, "504"))
                ]
            elif path.endswith("/estado-cuenta"):
                uid = path.split("/")[-2]
                if uid == B and fallar_b:
                    fallar_b = False
                    await route.fulfill(
                        status=503, json={"mensaje": "Prueba de recuperación de cuenta"}
                    )
                    return
                data = cuenta(uid, parse_qs(parsed.query))
            else:
                data = []
            await route.fulfill(json=data)

        await page.route("**/api/v1/**", responder)
        await page.goto(url + "/residente", timeout=45000)
        await expect(page.get_by_text("Cargo privado de unidad A", exact=True)).to_be_visible()
        await expect(
            page.get_by_role("region", name="Pagos en revisión del periodo")
        ).to_contain_text("PENDIENTE-A")
        form = page.get_by_role("form", name="Filtrar estado de cuenta")
        await form.get_by_label("Desde").fill("2026-10-01")
        await form.get_by_label("Hasta").fill("2026-10-31")
        await page.get_by_role("button", name="Consultar periodo").click()
        await expect(page.get_by_text("1–50 de 51 movimientos", exact=True)).to_be_visible()
        await page.get_by_role("button", name="Siguiente", exact=True).click()
        await expect(page.get_by_text("51–51 de 51 movimientos", exact=True)).to_be_visible()
        await page.get_by_role("button", name="Anterior", exact=True).click()
        await expect(page.get_by_text("Cargo privado de unidad A", exact=True)).to_be_visible()
        await page.get_by_role(
            "heading", name="Estado de cuenta", exact=True
        ).scroll_into_view_if_needed()
        Path("tmp").mkdir(exist_ok=True)
        await page.screenshot(path="tmp/con14-desktop.png")
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.get_by_role(
            "heading", name="Estado de cuenta", exact=True
        ).scroll_into_view_if_needed()
        await page.screenshot(path="tmp/con14-mobile.png")
        if not await page.evaluate("document.documentElement.scrollWidth <= innerWidth"):
            print(
                await page.evaluate(
                    """({inner:innerWidth,root:document.documentElement.scrollWidth,body:document.body.scrollWidth,x:scrollX,items:[...document.querySelectorAll('body *')].filter(e => {if(e.getBoundingClientRect().right <= innerWidth+1)return false;let p=e.parentElement;while(p&&p!==document.body){if(['auto','scroll','hidden','clip'].includes(getComputedStyle(p).overflowX))return false;p=p.parentElement}return true}).slice(0,8).map(e=>({tag:e.tagName,cls:e.className,width:e.getBoundingClientRect().width}))})"""
                )
            )
            raise AssertionError("La página desborda horizontalmente en móvil")
        await page.set_viewport_size({"width": 1440, "height": 1000})

        selector = page.get_by_label("Departamento:", exact=True)
        await selector.select_option(B)
        await expect(
            page.get_by_text("Prueba de recuperación de cuenta", exact=True)
        ).to_be_visible()
        await page.get_by_role("button", name="Reintentar", exact=True).click()
        await expect(
            page.get_by_text("Sin movimientos en este periodo", exact=True)
        ).to_be_visible()
        await expect(page.get_by_text("Cargo privado de unidad A", exact=True)).to_have_count(0)

        # Retener una respuesta ya recibida simula trabajo tardío aunque se aborte el fetch.
        await page.evaluate("""() => {
          const original = window.fetch;
          window.fetch = async (...args) => {
            const response = await original(...args);
            if (window.__retenerA && String(args[0]).includes('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa/estado-cuenta')) {
              window.__retenerA = false;
              await new Promise(r => window.__liberarA = r);
            }
            return response;
          };
          window.__retenerA = true;
        }""")
        await selector.select_option(A)
        await page.wait_for_function("typeof window.__liberarA === 'function'")
        await selector.select_option(B)
        await expect(
            page.get_by_text("Sin movimientos en este periodo", exact=True)
        ).to_be_visible()
        await page.evaluate("window.__liberarA()")
        await page.evaluate(
            "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
        )
        await expect(page.get_by_text("Cargo privado de unidad A", exact=True)).to_have_count(0)
        await expect(page.get_by_text("PENDIENTE-A", exact=False)).to_have_count(0)
        assert not errores, errores
        print(
            "CON-14 Chromium: rango, página, móvil, error/reintento y unidad/respuesta tardía: OK"
        )
        await browser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:3077")
    asyncio.run(verificar(parser.parse_args().url.rstrip("/")))
