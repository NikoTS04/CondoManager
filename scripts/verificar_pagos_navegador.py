"""Recorrido Chromium CON-22/70/42 contra una instancia DEMO aislada.

No arranca servicios ni modifica configuraciones. Requiere playwright y Chromium:
python -m pip install playwright; python -m playwright install chromium
"""

import argparse
import io
import json
from pathlib import Path
from uuid import uuid4

from PIL import Image
from playwright.sync_api import expect, sync_playwright


def entrar(page, url, email, password):
    page.goto(url + "/login")
    page.wait_for_load_state("networkidle")
    page.get_by_label("Correo electrónico").fill(email)
    page.get_by_label("Contraseña").fill(password)
    page.get_by_role("button", name="Iniciar sesión", exact=True).click()
    page.wait_for_url("**/residente*" if "moroso" in email else "**/junta*")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--confirmar-entorno-demo", action="store_true", required=True)
    parser.add_argument("--evidencia-dir", type=Path)
    parser.add_argument(
        "--comprobante-reinicio", help="Verificación de solo lectura después de reiniciar la API"
    )
    args = parser.parse_args()
    operacion = "BROWSER-" + uuid4().hex[:16]
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), "white").save(buffer, format="PNG")

    with sync_playwright() as playwright:
        expect.set_options(timeout=15000)
        browser = playwright.chromium.launch()
        residente = browser.new_context(accept_downloads=True)
        junta = browser.new_context(accept_downloads=True)
        page = residente.new_page()
        admin = junta.new_page()
        errores = []
        page.on("pageerror", lambda error: errores.append(str(error)))
        admin.on("pageerror", lambda error: errores.append(str(error)))
        entrar(page, args.url, "moroso402@villabonita3.pe", "Moroso123!")
        if args.comprobante_reinicio:
            with page.expect_response(
                lambda response: "/pagos/comprobantes" in response.url and response.status == 200
            ) as historial:
                page.reload()
            assert any(
                c["id"] == args.comprobante_reinicio and c["estado"] == "APROBADO"
                for c in historial.value.json()
            )
            page.get_by_role("tab", name="Pagos", exact=True).click()
            expect(page.get_by_text("Aprobado", exact=True)).to_be_visible()
            with page.expect_download() as descarga:
                page.get_by_role("button", name="Descargar voucher").first.click()
            assert descarga.value.suggested_filename.endswith(".png")
            browser.close()
            print(
                json.dumps(
                    {
                        "resultado": "correcto",
                        "reinicio": True,
                        "comprobante_id": args.comprobante_reinicio,
                    }
                )
            )
            return
        expect(page.get_by_text("Reservas bloqueadas por mora", exact=True)).to_be_visible()
        page.get_by_role("tab", name="Pagos", exact=True).click()
        page.get_by_label("Número de Operación Bancaria").fill(operacion)
        page.get_by_label("Monto Pagado").fill("170.00")
        page.locator('input[type="file"]').set_input_files(
            {
                "name": "evidencia.png",
                "mimeType": "image/png",
                "buffer": buffer.getvalue(),
            }
        )
        page.get_by_role("button", name="Reportar Pago", exact=True).click()
        with page.expect_response(
            lambda response: response.url.endswith("/pagos/reportar")
        ) as recibido:
            page.get_by_role("button", name="Confirmar y enviar").click()
        assert recibido.value.status == 202, recibido.value.text()
        id = recibido.value.json()["comprobante_id"]
        expect(page.get_by_text("Comprobante recibido", exact=True)).to_be_visible()
        with page.expect_download() as descarga:
            page.get_by_role("button", name="Descargar voucher").first.click()
        assert descarga.value.suggested_filename.endswith(".png")
        page.get_by_role("tab", name="Reservas", exact=True).click()
        expect(page.get_by_text("Reserva bloqueada por mora", exact=True)).to_be_visible()

        entrar(admin, args.url, "admin@villabonita3.pe", "Admin123!")
        admin.get_by_role("button", name="Conciliación", exact=False).click()
        fila = admin.locator("tr").filter(has_text=operacion)
        expect(fila).to_be_visible()
        fila.get_by_role("button", name="Observar", exact=True).click()
        admin.get_by_label("Motivo de la observación o rechazo").fill("Adjuntar imagen más legible")
        with admin.expect_response(lambda r: r.url.endswith(f"/pagos/{id}/conciliar")) as observada:
            admin.get_by_role("dialog").get_by_role(
                "button", name="Observar comprobante", exact=True
            ).click()
        assert observada.value.status == 200
        expect(fila.get_by_role("button", name="Aprobar", exact=True)).to_have_count(0)
        page.reload()
        page.get_by_role("tab", name="Pagos", exact=True).click()
        page.get_by_role("button", name="Subsanar voucher", exact=True).click()
        page.get_by_label("Nuevo voucher para subsanar").set_input_files(
            {
                "name": "corregido.png",
                "mimeType": "image/png",
                "buffer": buffer.getvalue(),
            }
        )
        with page.expect_response(
            lambda r: r.url.endswith(f"/pagos/{id}/voucher") and r.request.method == "PUT"
        ) as subsanada:
            page.get_by_role("button", name="Enviar subsanación", exact=True).click()
        assert subsanada.value.status == 202
        assert subsanada.value.json()["comprobante_id"] == id
        admin.reload()
        admin.get_by_role("button", name="Conciliación", exact=False).click()
        fila.get_by_role("button", name="Aprobar", exact=True).click()
        with admin.expect_response(
            lambda response: response.url.endswith(f"/pagos/{id}/conciliar")
        ) as aprobado:
            admin.get_by_role("dialog").get_by_role(
                "button", name="Aprobar comprobante", exact=True
            ).click()
        assert aprobado.value.status == 200, aprobado.value.text()
        assert aprobado.value.json()["departamento_habilitado_reservas"] is True
        page.get_by_role("tab", name="Reservas", exact=True).click()
        page.get_by_role("button", name="Actualizar solvencia").click()
        expect(page.get_by_role("button", name="Confirmar Reserva", exact=True)).to_be_enabled()
        expect(
            page.get_by_text("Tu departamento está al día y puedes realizar reservas.", exact=True)
        ).to_be_visible()
        page.reload()
        page.get_by_role("tab", name="Pagos", exact=True).click()
        expect(page.get_by_text("Aprobado", exact=True)).to_be_visible()
        page.get_by_role("tab", name="Avisos", exact=True).click()
        for _ in range(15):
            with page.expect_response(lambda r: "/notificaciones/logs" in r.url) as avisos:
                page.get_by_role("button", name="Actualizar avisos").click()
            if any(n["tipo_evento"] == "NOTIF_PAGO_CONCILIADO" for n in avisos.value.json()):
                break
            page.wait_for_timeout(1000)
        else:
            raise AssertionError("No se recuperó el aviso de aprobación")
        expect(page.get_by_text("Transporte simulado", exact=False).first).to_be_visible()
        if args.evidencia_dir:
            args.evidencia_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(
                path=str(args.evidencia_dir / "comprobante-persistido.png"), full_page=True
            )
            admin.screenshot(
                path=str(args.evidencia_dir / "revision-confirmada.png"), full_page=True
            )
        assert not errores, errores
        browser.close()
    print(
        json.dumps(
            {
                "resultado": "correcto",
                "comprobante_id": id,
                "verificado": [
                    "subida real",
                    "descarga privada",
                    "revision persistente",
                    "subsanacion con UUID conservado",
                    "aviso desde evento canonico",
                    "mora antes de aprobar",
                    "solvencia posterior",
                    "recarga del navegador",
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
