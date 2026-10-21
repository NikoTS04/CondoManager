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
    return new Response(JSON.stringify({ generadas: 2 }));
  });
  await api.fetchComprobantes(cid);
  assert.equal(new URL(solicitudes[0].url).searchParams.get("condominio_id"), cid);
  await api.enviarComunicadoMasivo("Aviso", "Mensaje de prueba", cid);
  assert.equal(JSON.parse(solicitudes[1].init.body).condominio_id, cid);
});

test("el cliente conserva códigos y detalles de un conflicto de horario", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({
    error_code: "HORARIO_NO_DISPONIBLE", mensaje: "El turno acaba de ocuparse.", detalles: { area_id: "area" },
  }), { status: 409 }));
  await assert.rejects(api.fetchDisponibilidad("area", "2026-12-01"),
    (error) => error.status === 409 && error.errorCode === "HORARIO_NO_DISPONIBLE" && error.detalles.area_id === "area");
  assert.equal((await api.crearReserva({})).errorCode, "HORARIO_NO_DISPONIBLE");
});

test("el comunicado confirma cola y conserva el número de avisos persistidos", async (t) => {
  t.mock.method(globalThis, "fetch", async () => new Response(JSON.stringify({ generadas: 3, estado_general: "EN_COLA" }), { status: 202 }));
  assert.deepEqual(await api.enviarComunicadoMasivo("Aviso", "Mensaje", "cid"), { ok: true, generadas: 3 });
});

test("reporte y subsanación usan multipart sin enviar claves privadas ni Content-Type manual", async (t) => {
  const archivo = new File(["voucher"], "pago.png", { type: "image/png" });
  const solicitudes = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    solicitudes.push({ url, init });
    return new Response(JSON.stringify({ codigo: "VOUCHER_EN_EVALUACION" }), { status: 200 });
  });
  const res = await api.reportarPago({ departamento_id: "unidad", banco: "BCP", numero_operacion: "1",
    fecha_operacion: "2026-10-15", monto: "10.00", archivo_voucher: archivo });
  assert.equal(res.duplicado, true);
  await api.subsanarVoucher("comprobante", archivo);
  assert.equal(solicitudes[0].init.method, "POST");
  assert.equal(solicitudes[1].init.method, "PUT");
  for (const { init } of solicitudes) {
    assert.equal(init.headers["Content-Type"], undefined);
    assert.equal(init.body.get("archivo_voucher").name, "pago.png");
    assert.equal(init.body.has("url_voucher"), false);
  }
  assert.deepEqual([...solicitudes[1].init.body.keys()], ["archivo_voucher"]);
});

test("alta, listado y estado de usuarios respetan el contexto y los métodos del contrato", async (t) => {
  const cid = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
  const uid = "8d3f2f64-1111-4222-8333-444455556666";
  const solicitudes = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    solicitudes.push({ url, init });
    return new Response(JSON.stringify({ id: uid, esta_activo: true }));
  });
  globalThis.window = {};
  globalThis.localStorage = { getItem: () => "token-prueba" };
  try {
    await api.listarUsuarios(cid, 25, 50);
    await api.crearUsuario(cid, { email: "nuevo@ejemplo.test", password: "Inicial123!" });
    await api.cambiarEstadoUsuario(cid, uid, false);
  } finally {
    delete globalThis.window;
    delete globalThis.localStorage;
  }
  const [listado, alta, estado] = solicitudes;
  assert.equal(listado.init.headers.Authorization, "Bearer token-prueba");
  assert.equal(new URL(listado.url).pathname.endsWith(`/condominios/${cid}/usuarios`), true);
  assert.equal(new URL(listado.url).searchParams.get("limit"), "25");
  assert.equal(alta.init.method, "POST");
  assert.equal(JSON.parse(alta.init.body).email, "nuevo@ejemplo.test");
  assert.equal(estado.init.method, "PATCH");
  assert.equal(new URL(estado.url).searchParams.get("condominio_id"), cid);
  assert.equal(JSON.parse(estado.init.body).esta_activo, false);
});

test("el login envía el contexto elegido y conserva el cuerpo del 409", async (t) => {
  const cid = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
  let capturada;
  t.mock.method(globalThis, "fetch", async (_url, init) => {
    capturada = init;
    return new Response(JSON.stringify({
      error_code: "CONTEXTO_REQUERIDO",
      detalles: { condominios: [{ id: cid, nombre: "Villa Bonita 3" }] },
    }), { status: 409 });
  });
  await assert.rejects(
    api.iniciarSesion("residente@ejemplo.test", "Secreta123!", cid),
    (error) => error.error_code === "CONTEXTO_REQUERIDO" && error.detalles.condominios[0].id === cid,
  );
  assert.equal(JSON.parse(capturada.body).condominio_id, cid);
});

test("consultar, asignar y revocar roles utiliza el recurso contextual y conserva el estado devuelto", async (t) => {
  const cid = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
  const uid = "8d3f2f64-1111-4222-8333-444455556666";
  const solicitudes = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    solicitudes.push({ url, init });
    assert.equal(init.headers.Authorization, "Bearer sesion-roles");
    return new Response(JSON.stringify({ usuario_id: uid, condominio_id: cid, rol: "AUDITOR", es_activo: init.method !== "DELETE" }));
  });
  globalThis.window = {};
  globalThis.localStorage = { getItem: () => "sesion-roles" };
  try {
    assert.equal((await api.consultarRolUsuario(cid, uid)).es_activo, true);
    assert.equal((await api.asignarRolUsuario(cid, uid, "AUDITOR")).rol, "AUDITOR");
    assert.equal((await api.revocarRolUsuario(cid, uid)).es_activo, false);
    for (const solicitud of solicitudes) {
      assert.equal(new URL(solicitud.url).pathname, `/api/v1/condominios/${cid}/usuarios/${uid}/rol`);
    }
    assert.equal(solicitudes[1].init.method, "PUT");
    assert.deepEqual(JSON.parse(solicitudes[1].init.body), { rol: "AUDITOR" });
    assert.equal(solicitudes[2].init.method, "DELETE");
    assert.equal(solicitudes[2].init.body, undefined);
  } finally {
    delete globalThis.window;
    delete globalThis.localStorage;
  }
});

test("un token revocado al gestionar roles notifica el cierre de sesión y propaga el rechazo", async (t) => {
  const eventos = [];
  globalThis.window = { dispatchEvent: (event) => eventos.push(event.type) };
  globalThis.localStorage = { getItem: () => "sesion-vieja" };
  t.mock.method(globalThis, "fetch", async () => new Response(
    JSON.stringify({ error_code: "SESION_REVOCADA", mensaje: "Los permisos cambiaron." }), { status: 401 },
  ));
  try {
    await assert.rejects(api.asignarRolUsuario("cid", "uid", "AUDITOR"), /Los permisos cambiaron/);
    await assert.rejects(api.listarEdificios("cid"), /Los permisos cambiaron/);
    assert.equal((await api.obtenerPresupuestoPorPeriodo("cid", "2026-10")).ok, false);
    assert.deepEqual(eventos, Array(3).fill("condomanager:sesion-revocada"));
  } finally {
    delete globalThis.window;
    delete globalThis.localStorage;
  }
});

test("los vínculos se gestionan por UUID sin enviar roles ni estados de cuenta", async (t) => {
  const cid = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
  const uid = "8d3f2f64-1111-4222-8333-444455556666";
  const did = "11111111-1111-4111-8111-111111111101";
  const solicitudes = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    solicitudes.push({ url, init });
    const vinculo = { usuario_id: uid, departamento_id: did, tipo_relacion: "INQUILINO", es_activo: init.method !== "DELETE" };
    return new Response(JSON.stringify(init.method ? vinculo : [vinculo]));
  });
  await api.listarVinculosUsuario(cid, uid);
  assert.equal((await api.asignarVinculoUsuario(cid, uid, did, "INQUILINO")).es_activo, true);
  assert.equal((await api.revocarVinculoUsuario(cid, uid, did)).es_activo, false);
  assert.equal(new URL(solicitudes[0].url).pathname, `/api/v1/condominios/${cid}/usuarios/${uid}/departamentos`);
  assert.equal(new URL(solicitudes[1].url).pathname, `/api/v1/condominios/${cid}/usuarios/${uid}/departamentos/${did}`);
  assert.equal(solicitudes[1].init.method, "PUT");
  assert.deepEqual(JSON.parse(solicitudes[1].init.body), { tipo_relacion: "INQUILINO" });
  assert.equal(solicitudes[2].init.method, "DELETE");
  assert.equal(solicitudes[2].init.body, undefined);
});

test("el catálogo administrativo transmite costo como cadena y el estado en su recurso propio", async (t) => {
  const cid = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
  const aid = "11111111-1111-4111-8111-111111111101";
  const solicitudes = [];
  t.mock.method(globalThis, "fetch", async (url, init) => {
    solicitudes.push({ url, init });
    return new Response(JSON.stringify({ id: aid, costo_reserva: "0.10", esta_activa: true }));
  });
  const datos = { nombre: "Sala", aforo_maximo: 12, costo_reserva: "0.10", hora_apertura: "08:00", hora_cierre: "22:00", tiempo_maximo_horas: 4, descripcion: null, edificio_id: null };
  await api.listarCatalogoAreas(cid, false, 25, 50);
  assert.equal(new URL(solicitudes[0].url).searchParams.get("esta_activa"), "false");
  assert.equal(new URL(solicitudes[0].url).searchParams.get("offset"), "50");
  await api.registrarArea(cid, datos);
  await api.configurarArea(cid, aid, datos);
  await api.cambiarEstadoArea(cid, aid, false);
  assert.equal(solicitudes[1].init.method, "POST");
  assert.equal(JSON.parse(solicitudes[1].init.body).costo_reserva, "0.10");
  assert.equal(solicitudes[2].init.method, "PUT");
  assert.equal(new URL(solicitudes[2].url).pathname, `/api/v1/condominios/${cid}/areas/${aid}`);
  assert.equal(solicitudes[3].init.method, "PATCH");
  assert.deepEqual(JSON.parse(solicitudes[3].init.body), { esta_activa: false });
  assert.equal(new URL(solicitudes[3].url).pathname.endsWith(`/${aid}/estado`), true);
});

test("las alertas de entrega usan la ruta y el método correctos y propagan errores", async (t) => {
  const cid = "3fa85f64-5717-4562-b3fc-2c963f66afa6";
  const solicitudes = [];
  const mock = t.mock.method(globalThis, "fetch", async (url, init) => {
    solicitudes.push({ url: String(url), init });
    return new Response(JSON.stringify([]));
  });
  await api.listarAlertasNotificacion(cid);
  const lista = new URL(solicitudes[0].url);
  assert.equal(lista.pathname.endsWith("/notificaciones/alertas"), true);
  assert.equal(lista.searchParams.get("condominio_id"), cid);
  assert.equal(solicitudes[0].init.method, undefined);
  await api.atenderAlertaNotificacion("alerta/1");
  assert.equal(new URL(solicitudes[1].url).pathname.endsWith("/notificaciones/alertas/alerta%2F1/atender"), true);
  assert.equal(solicitudes[1].init.method, "POST");
  mock.mock.mockImplementation(async () => new Response(
    JSON.stringify({ detail: { mensaje: "Acceso denegado" } }), { status: 403 },
  ));
  await assert.rejects(api.listarAlertasNotificacion(cid), /Acceso denegado/);
  await assert.rejects(api.atenderAlertaNotificacion("alerta"), /Acceso denegado/);
});
