import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

// Renderiza los componentes reales sin incorporar un runner ni dependencias nuevas.
const require = createRequire(import.meta.url);
function loadComponent(path) {
  const tsx = new URL(`../src/${path}.tsx`, import.meta.url);
  const file = existsSync(tsx) ? tsx : new URL(`../src/${path}.ts`, import.meta.url);
  const source = readFileSync(file, "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2022 },
  });
  const module = { exports: {} };
  new Function("require", "module", "exports", outputText)((id) => {
    if (id.startsWith("@/")) return loadComponent(id.slice(2));
    return require(id);
  }, module, module.exports);
  return module.exports;
}

const { ResumenCuenta } = loadComponent("features/residente/ResumenCuenta");
const { ResumenSection } = loadComponent("features/junta/ResumenSection");
const { MorasSection } = loadComponent("features/junta/MorasSection");
const { ResultadoPago } = loadComponent("components/domain/ResultadoPago");
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const depto = { id: "unidad-a", numero: "402", piso: 4, coeficiente: "0.6800", saldo_a_favor: "25.50", deuda_vencida: "123.45", estado_financiero: "EN_MORA", activo: true };

test("la cuenta muestra importes reales sin cuota ni periodo referencial", () => {
  const html = render(ResumenCuenta, { depto });
  assert.match(html, /123\.45/);
  assert.match(html, /25\.50/);
  assert.doesNotMatch(html, /141\.78|154\.29|2026-10|Referencial|Penalidades/);
  const faltante = render(ResumenCuenta, { depto: { ...depto, deuda_vencida: undefined } });
  assert.match(faltante, /No disponible/);
  assert.doesNotMatch(faltante, /0\.00/);
  assert.match(render(ResumenCuenta, { depto: { ...depto, deuda_vencida: "0.00" } }), /0\.00/);
});

test("el resumen no confunde presupuesto sin consultar con sin aprobar", () => {
  const html = render(ResumenSection, { loading: false, departamentos: [depto], comprobantesPendientes: 3, presupuesto: null, onNavigate() {} });
  assert.match(html, /Consultar presupuesto/);
  assert.match(html, />3<\/p>/);
  assert.doesNotMatch(html, /Sin aprobar|Sin presupuesto aprobado|En seguimiento/);
});

test("moras solo incluye unidades activas en mora y no ofrece simulaciones", () => {
  const html = render(MorasSection, { loading: false, departamentos: [depto, { ...depto, id: "b", numero: "999", activo: false }, { ...depto, id: "c", numero: "888", estado_financiero: "AL_DIA" }] });
  assert.match(html, /Departamento 402/);
  assert.doesNotMatch(html, /999|888|Evaluar moras|Simulación|<button/);
  assert.match(render(MorasSection, { loading: false, departamentos: [] }), /Sin unidades activas en mora/);
});

test("la carga no muestra un vacío ni saldos como si la consulta hubiera terminado", () => {
  const html = render(MorasSection, { loading: true, departamentos: [] });
  assert.match(html, /Cargando/);
  assert.doesNotMatch(html, /Sin unidades activas en mora/);
});

const recibo = { comprobante_id: "pago-prueba", estado_final: "APROBADO", monto_imputado: "40.00",
  nuevo_saldo_departamento: "60.00", saldo_a_favor_generado: "0.00",
  departamento_habilitado_reservas: false, motivo_rechazo: null };

test("el recibo parcial distingue abono, deuda histórica y bloqueo sin inventar moneda", () => {
  const html = render(ResultadoPago, { resultado: recibo });
  assert.match(html, /40\.00/);
  assert.match(html, /60\.00/);
  assert.match(html, /Deuda al revisar/);
  assert.match(html, /no elimina el bloqueo/);
  assert.doesNotMatch(html, /S\/|USD|saldo actual/i);
});

test("el recibo de excedente no convierte el crédito en otro pago", () => {
  const html = render(ResultadoPago, { resultado: { ...recibo, monto_imputado: "100.00",
    nuevo_saldo_departamento: "0.00", saldo_a_favor_generado: "20.00", departamento_habilitado_reservas: true } });
  assert.match(html, /Crédito de este pago/);
  assert.match(html, /20\.00/);
  assert.match(html, /vuelve a comprobar la solvencia actual/);
});

test("observación y rechazo muestran instrucciones distintas y escapan el motivo", () => {
  const observado = render(ResultadoPago, { resultado: { ...recibo, estado_final: "OBSERVADO",
    motivo_rechazo: "<script>ilegible</script>" } });
  assert.match(observado, /Subsanar voucher/);
  assert.match(observado, /&lt;script&gt;/);
  assert.doesNotMatch(observado, /<script>/);
  const rechazado = render(ResultadoPago, { resultado: { ...recibo, estado_final: "RECHAZADO", motivo_rechazo: "No acreditado" } });
  assert.match(rechazado, /decisión es definitiva/);
  assert.doesNotMatch(rechazado, /Subsanar voucher/);
});
