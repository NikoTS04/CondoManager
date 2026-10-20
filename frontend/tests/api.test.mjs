import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/lib/api.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
});
const api = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

test("todas las consultas protegidas envían Bearer y propagan rechazos", async (t) => {
  t.mock.method(globalThis, "fetch", async (_url, init) => {
    assert.equal(init.headers.Authorization, "Bearer token-prueba");
    return new Response(JSON.stringify({ detail: { mensaje: "Acceso denegado" } }), { status: 403 });
  });
  globalThis.window = {};
  globalThis.localStorage = { getItem: () => "token-prueba" };
  try {
    for (const consulta of [
      api.fetchDepartamentos, api.fetchAreasComunes, api.fetchReservas,
      api.fetchComprobantes, api.fetchNotificaciones, api.obtenerSesion,
    ]) await assert.rejects(consulta(), /Acceso denegado/);
  } finally {
    delete globalThis.window;
    delete globalThis.localStorage;
  }
});

test("las mutaciones denegadas o sin red nunca devuelven éxitos simulados", async (t) => {
  const mock = t.mock.method(globalThis, "fetch", async () => new Response(
    JSON.stringify({ detail: { mensaje: "Acceso denegado" } }), { status: 403 },
  ));
  const acciones = [
    () => api.crearReserva({}), () => api.reportarPago({}),
    () => api.cancelarReserva("reserva"), () => api.conciliarComprobante("pago", "APROBADO"),
    () => api.enviarComunicadoMasivo("Aviso", "Mensaje", "condominio"),
  ];
  for (const accion of acciones) assert.equal((await accion()).ok, false);
  mock.mock.mockImplementation(async () => { throw new TypeError("Sin conexión"); });
  for (const accion of acciones) assert.equal((await accion()).ok, false);
});

test("las consultas y los comunicados usan el condominio seleccionado", async (t) => {
  const cid = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
  const solicitudes = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    solicitudes.push({ url, init });
    return new Response(JSON.stringify({ notificaciones_generadas: 2 }));
  });
  await api.fetchComprobantes(cid);
  assert.equal(new URL(solicitudes[0].url).searchParams.get("condominio_id"), cid);
  await api.enviarComunicadoMasivo("Aviso", "Mensaje de prueba", cid);
  assert.equal(JSON.parse(solicitudes[1].init.body).condominio_id, cid);
});
