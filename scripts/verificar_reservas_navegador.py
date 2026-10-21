"""CON-73/74: recorrido Chromium contra un entorno demo explícitamente aislado."""

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def entrar(page, url):
    page.goto(url + "/login")
    page.get_by_label("Correo electrónico").fill("residente102@villabonita3.pe")
    page.get_by_label("Contraseña").fill("Residente123!")
    page.get_by_role("button", name="Iniciar sesión", exact=True).click()
    page.wait_for_url("**/residente*")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://localhost:3000")
    parser.add_argument("--confirmar-entorno-demo", action="store_true", required=True)
    parser.add_argument("--evidencia-dir", type=Path)
    parser.add_argument(
        "--reserva-reinicio", help="UUID a verificar después de reiniciar API/worker/BD"
    )
    args = parser.parse_args()
    with sync_playwright() as p:
        expect.set_options(timeout=15000)
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        errores = []
        page.on("pageerror", lambda e: errores.append(str(e)))
        entrar(page, args.url)
        if args.reserva_reinicio:
            with page.expect_response(
                lambda r: "/reservas?" in r.url and r.status == 200
            ) as listado:
                page.reload()
            assert any(r["id"] == args.reserva_reinicio for r in listado.value.json())
            rid = args.reserva_reinicio
        else:
            expect(page.get_by_role("button", name="Confirmar Reserva", exact=True)).to_be_enabled()
            page.get_by_label("Fecha de Reserva").fill(
                (date.today() + timedelta(days=10)).isoformat()
            )
            page.get_by_label("Hora Inicio").fill("14:00")
            page.get_by_label("Hora Fin").fill("16:00")
            expect(page.get_by_role("button", name="Confirmar Reserva", exact=True)).to_be_enabled()
            with page.expect_response(
                lambda r: r.url.endswith("/reservas") and r.request.method == "POST"
            ) as creado:
                page.get_by_role("button", name="Confirmar Reserva", exact=True).click()
            assert creado.value.status == 201, creado.value.text()
            rid = creado.value.json()["id"]
            expect(page.get_by_text("Reserva realizada", exact=True)).to_be_visible()
            with page.expect_response(
                lambda r: "/reservas?" in r.url and r.status == 200
            ) as listado:
                page.reload()
            assert any(r["id"] == rid for r in listado.value.json())
        page.get_by_role("tab", name="Avisos", exact=True).click()
        # La cola es asíncrona: refrescar desde la API, no inventar una confirmación local.
        for _ in range(10):
            with page.expect_response(lambda r: "/notificaciones/logs" in r.url) as avisos:
                page.get_by_role("button", name="Actualizar avisos").click()
            if any("reserva" in n["tipo_evento"].lower() for n in avisos.value.json()):
                break
            page.wait_for_timeout(1000)
        else:
            raise AssertionError("El worker no produjo un aviso persistente de la reserva")
        expect(page.get_by_text("Transporte simulado", exact=False).first).to_be_visible()
        if args.evidencia_dir:
            args.evidencia_dir.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(args.evidencia_dir / "avisos-persistidos.png"), full_page=True)
        if not args.reserva_reinicio:
            page.get_by_role("tab", name="Reservas de Áreas Comunes").click()
            page.get_by_role("button", name="Cancelar", exact=True).first.click()
            with page.expect_response(
                lambda r: r.url.endswith(f"/reservas/{rid}/cancelar")
            ) as cancelada:
                page.get_by_role("dialog").get_by_role(
                    "button", name="Sí, cancelar reserva", exact=True
                ).click()
            assert cancelada.value.status == 200, cancelada.value.text()
            assert cancelada.value.json()["ajuste_economico"]["estado"] == "NO_APLICA"
            expect(page.get_by_text("Cancelada", exact=True)).to_be_visible()
        assert not errores, errores
        browser.close()
    print(
        json.dumps(
            {
                "resultado": "correcto",
                "reserva_id": rid,
                "reinicio": bool(args.reserva_reinicio),
                "transporte": "SIMULADO",
            }
        )
    )


if __name__ == "__main__":
    main()
