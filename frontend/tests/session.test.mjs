import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import ts from "typescript";

const source = await readFile(new URL("../src/lib/session.ts", import.meta.url), "utf8");
const { outputText } = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ES2022, target: ts.ScriptTarget.ES2022 },
});
const { isSessionUser, seleccionarUnidad, etiquetaResidente, portalInicial } = await import(
  `data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`
);
const a = "11111111-1111-4111-8111-111111111101";
const b = "11111111-1111-4111-8111-111111111102";
const c = "11111111-1111-4111-8111-111111111103";
const user = {
  id: "residente", email: "residente@ejemplo.test", nombre: "Ana", apellido: "Pérez",
  rol: "RESIDENTE", condominio_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  departamentos: [
    { departamento_id: a, numero: "102", tipo_relacion: "PROPIETARIO_TITULAR", es_activo: true },
    { departamento_id: b, numero: "504", tipo_relacion: "INQUILINO", es_activo: true },
    { departamento_id: c, numero: "302", tipo_relacion: "COPROPIETARIO", es_activo: false },
  ],
};

test("el perfil v2 permite relaciones mixtas y redirige con rol RESIDENTE", () => {
  assert.ok(isSessionUser(user));
  assert.equal(portalInicial(user.rol), "/residente");
  for (const rol of ["SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"]) assert.equal(portalInicial(rol), "/junta");
  assert.equal(etiquetaResidente(user, a), "Propietario");
  assert.equal(etiquetaResidente(user, b), "Inquilino");
});

test("sesiones antiguas o roles desconocidos no son restaurables", () => {
  for (const rol of ["PROPIETARIO", "INQUILINO", "DESCONOCIDO", "__proto__"]) {
    assert.equal(isSessionUser({ ...user, rol }), false);
  }
  assert.equal(isSessionUser({ ...user, departamentos: ["102"] }), false);
  assert.equal(isSessionUser({ ...user, condominio_id: null }), false);
  assert.ok(isSessionUser({ ...user, rol: "SUPERADMIN", condominio_id: null, departamentos: [] }));
});

test("restaurar selección guardada y cambiar unidad solo usa vínculos activos", () => {
  assert.equal(seleccionarUnidad(user, null, b), b);
  assert.equal(seleccionarUnidad(user, b, a), b);
  assert.equal(seleccionarUnidad(user, c, b), b);
  assert.equal(seleccionarUnidad(user, "unidad-ajena", "otra-ajena"), a);
  assert.equal(seleccionarUnidad({ ...user, departamentos: [] }, a), "");
});

test("el catálogo confirma la selección y no confunde números con UUID", () => {
  assert.equal(seleccionarUnidad(user, "504", a, [a, b]), a);
  assert.equal(seleccionarUnidad(user, b, a, [a]), a);
  const admin = { ...user, rol: "ADMIN_JUNTA", departamentos: [] };
  assert.equal(seleccionarUnidad(admin, c, a, [a, b]), a);
  assert.equal(seleccionarUnidad(admin, b, a, [a, b]), b);
});

test("unidades del mismo número en edificios distintos se seleccionan por UUID", () => {
  const repetidos = { ...user, departamentos: user.departamentos.map((v) => ({ ...v, numero: "101" })) };
  assert.equal(seleccionarUnidad(repetidos, b, a, [a, b]), b);
  assert.equal(seleccionarUnidad(repetidos, "101", a, [a, b]), a);
  assert.equal(etiquetaResidente(repetidos, b), "Inquilino");
});
