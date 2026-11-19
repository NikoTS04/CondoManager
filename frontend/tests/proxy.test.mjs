import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/app/api/v1/[...path]/route.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
});
const proxy = await import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);

function entorno(t, valores) {
  const anteriores = Object.fromEntries(Object.keys(valores).map((k) => [k, process.env[k]]));
  Object.assign(process.env, valores);
  t.after(() => {
    for (const [k, valor] of Object.entries(anteriores)) {
      if (valor === undefined) delete process.env[k]; else process.env[k] = valor;
    }
  });
}

test("binding runtime, multipart, autorización, query y respuesta privada", async (t) => {
  entorno(t, { APP_URL: "https://binding-interno.test" });
  let enviada;
  t.mock.method(globalThis, "fetch", async (url, init) => {
    enviada = { url, init };
    return new Response("pdf-prueba", { headers: {
      "Content-Type": "application/pdf", "Content-Disposition": "attachment; filename=prueba.pdf",
      "Set-Cookie": "no-propagar", "Location": "https://binding-interno.test",
    } });
  });
  const response = await proxy.POST(new Request("https://portal.test/api/v1/pagos/reportar?condominio_id=cid", {
    method: "POST", body: "multipart-prueba", headers: {
      "Content-Type": "multipart/form-data; boundary=abc", Authorization: "Bearer prueba",
      "Idempotency-Key": "uuid", Cookie: "no-propagar",
    },
  }), { params: { path: ["pagos", "reportar"] } });
  assert.equal(enviada.url.href, "https://binding-interno.test/api/v1/pagos/reportar?condominio_id=cid");
  assert.equal(enviada.init.headers.get("authorization"), "Bearer prueba");
  assert.equal(enviada.init.headers.get("idempotency-key"), "uuid");
  assert.equal(enviada.init.headers.get("cookie"), null);
  assert.equal(new TextDecoder().decode(enviada.init.body), "multipart-prueba");
  assert.equal(enviada.init.redirect, "manual");
  assert.equal(await response.text(), "pdf-prueba");
  assert.equal(response.headers.get("cache-control"), "private, no-store");
  assert.equal(response.headers.get("set-cookie"), null);
  assert.equal(response.headers.get("location"), null);
});

test("Vercel sin binding, ruta insegura y tamaño excesivo fallan sin contactar API", async (t) => {
  entorno(t, { VERCEL: "1", APP_URL: "" });
  const fetch = t.mock.method(globalThis, "fetch", async () => { throw Error("no llamar"); });
  const request = () => new Request("https://portal.test/api/v1/pagos");
  assert.equal((await proxy.GET(request(), { params: { path: ["pagos"] } })).status, 503);
  process.env.APP_URL = "https://binding.test";
  assert.equal((await proxy.GET(request(), { params: { path: [".."] } })).status, 400);
  const grande = new Request("https://portal.test/api/v1/pagos", {
    method: "POST", body: new Uint8Array(4 * 1024 * 1024 + 1),
  });
  assert.equal((await proxy.POST(grande, { params: { path: ["pagos"] } })).status, 413);
  assert.equal(fetch.mock.callCount(), 0);
});

test("propaga denegaciones; no sigue redirecciones ni divulga fallos de red", async (t) => {
  entorno(t, { APP_URL: "https://binding.test" });
  const mock = t.mock.method(globalThis, "fetch", async () => new Response('{"error_code":"ACCESO_DENEGADO"}', { status: 403 }));
  const run = () => proxy.GET(new Request("https://portal.test/api/v1/pagos"), { params: { path: ["pagos"] } });
  assert.equal((await run()).status, 403);
  mock.mock.mockImplementation(async () => new Response(null, { status: 302, headers: { Location: "https://secreto.test" } }));
  const redirect = await run();
  assert.equal(redirect.status, 502);
  assert.equal(redirect.headers.get("location"), null);
  mock.mock.mockImplementation(async () => { throw Error("credencial-secreta"); });
  const fallida = await run();
  assert.equal(fallida.status, 503);
  assert.equal((await fallida.text()).includes("credencial-secreta"), false);
});
