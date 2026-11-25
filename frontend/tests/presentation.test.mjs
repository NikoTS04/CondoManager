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
const { ConciliacionSection } = loadComponent("features/junta/ConciliacionSection");
const render = (component, props) => renderToStaticMarkup(React.createElement(component, props));
const { ComunicadoEditor, ResolucionIncierta, CorreoOperacion } = loadComponent("features/junta/CorreoOperacion");

test("correo exige previsualizar y resolver incertidumbre sin reenvío ciego", () => {
  const editor = render(ComunicadoEditor, { cid: "cid", onActualizada() {} });
  assert.match(editor, /Previsualizar audiencia/);
  assert.doesNotMatch(editor, /Confirmar envío a/);
  assert.match(editor, /Solo correo/);
  const resolver = render(ResolucionIncierta, {
    aviso: { id: "nid", ciclo: 1, intentos: 1 }, onActualizada() {},
  });
  assert.match(resolver, /Revisa primero el intento en Mailjet/);
  assert.match(resolver, /Referencia y motivo de la revisión/);
  assert.match(resolver, /Registrar resolución auditada/);
});

test("la supervisión en carga no inventa un estado saludable ni habilita reactivación al auditor", () => {
  const html = render(CorreoOperacion, { cid: "cid", isAuditor: true });
  assert.match(html, /Consultando operación/);
  assert.doesNotMatch(html, /Proveedor habilitado|Reactivar con auditoría|Guardar política/);
});
const depto = { id: "unidad-a", numero: "402", piso: 4, coeficiente: "0.6800", saldo_a_favor: "25.50", deuda_vencida: "123.45", estado_financiero: "EN_MORA", activo: true };

test("la bandeja conserva filtros etiquetados durante carga sin mostrar éxitos ni vacíos", () => {
  const html = render(ConciliacionSection, {
    condominioId: "cid", loading: true, comprobantes: [], departamentos: [depto],
    isAuditor: true, onDecide() {},
  });
  assert.match(html, /Cargando comprobantes/);
  assert.doesNotMatch(html, /Sin resultados|Aprobar|Rechazar/);
});

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
  // Comprueba el escape de HTML con ambas variantes de mayúsculas del marcador.
  for (const motivo of ["<script>ilegible</script>", "<SCRIPT>ilegible</SCRIPT>"]) {
    const observado = render(ResultadoPago, { resultado: { ...recibo, estado_final: "OBSERVADO",
      motivo_rechazo: motivo } });
    assert.match(observado, /Subsanar voucher/);
    assert.match(observado, /&lt;script&gt;/i);
    assert.doesNotMatch(observado, /<script\b/i);
  }
  const rechazado = render(ResultadoPago, { resultado: { ...recibo, estado_final: "RECHAZADO", motivo_rechazo: "No acreditado" } });
  assert.match(rechazado, /decisión es definitiva/);
  assert.doesNotMatch(rechazado, /Subsanar voucher/);
});

// CON-68: salud y alertas visibles
const { PanelSalud, ListaAlertas, SaludAlertasSection, formatDuracion } = loadComponent("features/junta/SaludAlertasSection");
const salud = {
  perfil: "production", estado_general: "degradado", generado_en: "2026-11-24T15:00:00Z",
  componentes: [
    { componente: "api", estado: "ok" }, { componente: "postgresql", estado: "error" },
    { componente: "redis", estado: "deshabilitado" }, { componente: "correo", estado: "ok" },
  ],
  jobs: [
    { nombre: "notificaciones", inicio: "2026-11-24T03:00:00Z", fin: "2026-11-24T03:01:05Z", duracion_segundos: 65, resultado: "COMPLETADO" },
    { nombre: "diario", inicio: null, fin: null, duracion_segundos: null, resultado: "SIN_REGISTRO" },
  ],
};

test("la salud distingue componente caído de deshabilitado y muestra el resultado de los jobs", () => {
  const html = render(PanelSalud, { salud, cargando: false, error: null });
  assert.match(html, /PostgreSQL/);
  assert.match(html, /Con error/);
  assert.match(html, /Deshabilitado en este perfil/);
  assert.match(html, /Hay componentes con error/);
  assert.match(html, /Completado/);
  assert.match(html, /1 min 5 s/);
  assert.match(html, /Sin registro/);
});

test("la salud en carga o con error no inventa un estado operativo", () => {
  const cargando = render(PanelSalud, { salud: null, cargando: true, error: null });
  assert.match(cargando, /Consultando salud/);
  assert.doesNotMatch(cargando, /Operativo/);
  assert.match(render(PanelSalud, { salud: null, cargando: false, error: "No pudimos consultar la salud del sistema." }), /No pudimos consultar/);
});

test("cada alerta muestra componente, operación y referencia de diagnóstico", () => {
  const base = { estado: "ABIERTA", atendida_en: null, creada_en: "2026-11-24T15:00:00Z", tipo: "X", condominio_id: null };
  const html = render(ListaAlertas, {
    cargando: false, error: null, alertas: [
      { ...base, id: "1", componente: "job", operacion: "diario", departamento_numero: null, mensaje: "El proceso «diario» falló.",
        referencia_diagnostico: { origen_tipo: "JOB", origen_id: "diario", referencia_correlacion: null } },
      { ...base, id: "2", componente: "correo", operacion: "NOTIF_COMUNICADO_GENERAL", departamento_numero: "402", mensaje: "Sin entrega.",
        referencia_diagnostico: { origen_tipo: "CORREO", origen_id: "abc", referencia_correlacion: "corr-82" } },
    ],
  });
  assert.match(html, /Proceso programado/);
  assert.match(html, /JOB:diario/);
  assert.match(html, /Sin correlación aún/);
  assert.match(html, /NOTIF_COMUNICADO_GENERAL/);
  assert.match(html, /Dpto\. 402/);
  assert.match(html, /CORREO:abc/);
  assert.match(html, /corr-82/);
});

test("las alertas vacías o en carga no se confunden", () => {
  assert.match(render(ListaAlertas, { alertas: [], cargando: false, error: null }), /Sin alertas/);
  const cargando = render(ListaAlertas, { alertas: null, cargando: true, error: null });
  assert.match(cargando, /Cargando alertas/);
  assert.doesNotMatch(cargando, /Sin alertas/);
});

test("solo el rol global ve el panel de salud", () => {
  assert.match(render(SaludAlertasSection, { esSuperAdmin: true, condominioId: null }), /Estado de componentes/);
  const junta = render(SaludAlertasSection, { esSuperAdmin: false, condominioId: "cid" });
  assert.doesNotMatch(junta, /Estado de componentes/);
  assert.match(junta, /Alertas/);
  assert.equal(formatDuracion(null), "—");
});
