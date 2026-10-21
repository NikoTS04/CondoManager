import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/lib/api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
});
const api = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("fetchNotificaciones envía condominio_id y filtros de departamento, estado, canal y origen", async (t) => {
  const cid = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
  const did = "11111111-1111-4111-8111-111111111101";
  const solicitudes = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    solicitudes.push({ url, init });
    return new Response(
      JSON.stringify([
        {
          id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
          condominio_id: cid,
          departamento_id: did,
          origen_tipo: "COMUNICADO",
          tipo_evento: "COMUNICADO_MASIVO",
          canal: "EMAIL",
          destinatario: "residente@ejemplo.test",
          asunto: "Corte de agua",
          cuerpo: "Mantenimiento programado.",
          estado: "ENVIADO",
          intentos: 1,
          ciclo: 1,
          transporte_simulado: true,
          creado_en: "2026-10-20T12:00:00Z",
          actualizado_en: "2026-10-20T12:00:00Z",
        },
      ]),
      { status: 200 }
    );
  });
  globalThis.window = {};
  globalThis.localStorage = { getItem: () => "token-junta" };
  try {
    const resultado = await api.fetchNotificaciones(cid, {
      departamento_id: did,
      estado: "ENVIADO",
      canal: "EMAIL",
      origen_tipo: "COMUNICADO",
      limit: 20,
      offset: 0,
    });
    assert.equal(resultado.length, 1);
    assert.equal(resultado[0].estado, "ENVIADO");
    assert.equal(resultado[0].ciclo, 1);
    assert.equal(resultado[0].transporte_simulado, true);
    const parsed = new URL(solicitudes[0].url);
    assert.equal(parsed.pathname, "/api/v1/notificaciones/logs");
    assert.equal(parsed.searchParams.get("condominio_id"), cid);
    assert.equal(parsed.searchParams.get("departamento_id"), did);
    assert.equal(parsed.searchParams.get("estado"), "ENVIADO");
    assert.equal(parsed.searchParams.get("canal"), "EMAIL");
    assert.equal(parsed.searchParams.get("origen_tipo"), "COMUNICADO");
    assert.equal(parsed.searchParams.get("limit"), "20");
    assert.equal(parsed.searchParams.get("offset"), "0");
    assert.equal(solicitudes[0].init.headers.Authorization, "Bearer token-junta");
  } finally {
    delete globalThis.window;
    delete globalThis.localStorage;
  }
});

test("fetchNotificacionDetalle y fetchMisNotificaciones consultan los endpoints reales con Bearer", async (t) => {
  const nid = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const did = "11111111-1111-4111-8111-111111111101";
  const solicitudes = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    solicitudes.push({ url, init });
    if (String(url).includes(`/notificaciones/logs/${nid}`)) {
      return new Response(
        JSON.stringify({
          id: nid,
          tipo_evento: "COMUNICADO_MASIVO",
          canal: "EMAIL",
          destinatario: "residente@ejemplo.test",
          estado: "ENTREGADO",
          intentos: 1,
          ciclo: 2,
          creado_en: "2026-10-20T12:00:00Z",
          actualizado_en: "2026-10-20T12:00:00Z",
          historial_intentos: [
            {
              id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
              notificacion_id: nid,
              ciclo: 1,
              numero: 1,
              worker_id: "worker-1",
              transporte: "SIMULADO",
              transporte_simulado: true,
              resultado: "FALLO_DEFINITIVO",
              iniciado_en: "2026-10-20T12:00:01Z",
              finalizado_en: "2026-10-20T12:00:02Z",
            },
            {
              id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
              notificacion_id: nid,
              ciclo: 2,
              numero: 1,
              worker_id: "worker-1",
              transporte: "SIMULADO",
              transporte_simulado: true,
              resultado: "ACEPTADO",
              iniciado_en: "2026-10-20T12:05:01Z",
              finalizado_en: "2026-10-20T12:05:02Z",
            },
          ],
        }),
        { status: 200 }
      );
    }
    return new Response(JSON.stringify([]), { status: 200 });
  });
  globalThis.window = {};
  globalThis.localStorage = { getItem: () => "token-residente" };
  try {
    const detalle = await api.fetchNotificacionDetalle(nid);
    assert.equal(detalle.id, nid);
    assert.equal(detalle.ciclo, 2);
    assert.equal(detalle.historial_intentos.length, 2);
    assert.equal(detalle.historial_intentos[0].ciclo, 1);
    assert.equal(detalle.historial_intentos[1].ciclo, 2);

    await api.fetchMisNotificaciones(did, 15, 5);
    const misUrl = new URL(solicitudes[1].url);
    assert.equal(misUrl.pathname, "/api/v1/notificaciones/mis-notificaciones");
    assert.equal(misUrl.searchParams.get("departamento_id"), did);
    assert.equal(misUrl.searchParams.get("limit"), "15");
    assert.equal(misUrl.searchParams.get("offset"), "5");
  } finally {
    delete globalThis.window;
    delete globalThis.localStorage;
  }
});

test("alertas administrativas y reenvío manual respetan contratos y errores sin simular éxito", async (t) => {
  const cid = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
  const aid = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
  const nid = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
  const solicitudes = [];
  const mock = t.mock.method(globalThis, "fetch", async (url, init) => {
    solicitudes.push({ url, init });
    return new Response(
      JSON.stringify({
        id: aid,
        condominio_id: cid,
        notificacion_id: nid,
        tipo: "NOTIFICACION_FALLIDA",
        severidad: "ALTA",
        mensaje: "Agotó intentos",
        atendida_en: "2026-10-20T12:10:00Z",
        creado_en: "2026-10-20T12:00:00Z",
      }),
      { status: 200 }
    );
  });

  await api.fetchAlertasNotificaciones(cid, true);
  const alertaUrl = new URL(solicitudes[0].url);
  assert.equal(alertaUrl.pathname, "/api/v1/notificaciones/alertas");
  assert.equal(alertaUrl.searchParams.get("condominio_id"), cid);
  assert.equal(alertaUrl.searchParams.get("solo_abiertas"), "true");

  const atendida = await api.atenderAlertaNotificacion(aid);
  assert.equal(atendida.ok, true);
  assert.equal(new URL(solicitudes[1].url).pathname, `/api/v1/notificaciones/alertas/${aid}/atender`);
  assert.equal(solicitudes[1].init.method, "POST");

  const reenviada = await api.reenviarNotificacion(nid, "nuevo@ejemplo.test");
  assert.equal(reenviada.ok, true);
  assert.equal(new URL(solicitudes[2].url).pathname, `/api/v1/notificaciones/reenviar/${nid}`);
  assert.deepEqual(JSON.parse(solicitudes[2].init.body), {
    nuevo_destinatario: "nuevo@ejemplo.test",
  });

  mock.mock.mockImplementation(
    async () =>
      new Response(
        JSON.stringify({
          detail: {
            error_code: "REENVIO_NO_PERMITIDO",
            mensaje: "Solo se permite reenviar notificaciones en FALLIDO_PERMANENTE.",
          },
        }),
        { status: 409 }
      )
  );
  const rechazo = await api.reenviarNotificacion(nid);
  assert.equal(rechazo.ok, false);
  assert.match(rechazo.error, /FALLIDO_PERMANENTE/);

  const alertaDenegada = await api.atenderAlertaNotificacion(aid);
  assert.equal(alertaDenegada.ok, false);
});
