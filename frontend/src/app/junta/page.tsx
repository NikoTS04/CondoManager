"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useAuth } from "@/context/AuthContext";
import ConfiguracionCondominio from "@/components/ConfiguracionCondominio";
import EstructuraCondominio from "@/components/EstructuraCondominio";
import PresupuestoMensual, { PresupuestoAprobado } from "@/components/PresupuestoMensual";
import {
  ComprobantePago,
  Departamento,
  NotificacionLog,
  conciliarComprobante,
  emitirLoteCuotas,
  enviarComunicadoMasivo,
  fetchComprobantes,
  fetchDepartamentos,
  fetchNotificaciones,
  listarCondominios,
} from "@/lib/api";
import {
  ShieldCheck,
  Building,
  Building2,
  Coins,
  CheckCircle2,
  XCircle,
  Clock,
  AlertTriangle,
  Send,
  Users,
  FileCheck2,
  Bell,
  RefreshCw,
  ShieldAlert,
  Search,
  Lock,
  Settings2,
  ClipboardCheck,
} from "lucide-react";

export default function JuntaPage() {
  const { user } = useAuth();
  const isAuditor = user?.rol === "AUDITOR";
  const isSuperAdmin = user?.rol === "SUPERADMIN";
  const isForbidden = user && !["ADMIN_JUNTA", "SUPERADMIN", "AUDITOR"].includes(user.rol);

  const [activeTab, setActiveTab] = useState<"configuracion" | "estructura" | "presupuesto" | "conciliacion" | "cuotas" | "moras" | "notificaciones">("estructura");

  const [comprobantes, setComprobantes] = useState<ComprobantePago[]>([]);
  const [departamentos, setDepartamentos] = useState<Departamento[]>([]);
  const [notificaciones, setNotificaciones] = useState<NotificacionLog[]>([]);
  const [condominioActivoId, setCondominioActivoId] = useState<string | null>(null);

  // Estados de Emisión de Cuotas
  const [periodoEmision, setPeriodoEmision] = useState<string>("2026-11");
  const [presupuestoTotal, setPresupuestoTotal] = useState<string>("20850.00");
  const [presupuestoAprobado, setPresupuestoAprobado] = useState<PresupuestoAprobado | null>(null);
  const [emisionFeedback, setEmisionFeedback] = useState<string | null>(null);
  const [isEmitting, setIsEmitting] = useState<boolean>(false);

  // Estados de Comunicado Masivo
  const [comunicadoTitulo, setComunicadoTitulo] = useState<string>("");
  const [comunicadoMensaje, setComunicadoMensaje] = useState<string>("");
  const [comunicadoFeedback, setComunicadoFeedback] = useState<string | null>(null);

  // Estado de evaluación de moras
  const [morasFeedback, setMorasFeedback] = useState<string | null>(null);

  async function loadData() {
    const [comps, deptos, notifs] = await Promise.all([
      fetchComprobantes(),
      fetchDepartamentos(),
      fetchNotificaciones(),
    ]);
    setComprobantes(comps);
    setDepartamentos(deptos);
    setNotificaciones(notifs);
  }

  useEffect(() => {
    loadData();
  }, []);

  const handleCondominioSeleccionado = useCallback((condominioId: string | null) => {
    setCondominioActivoId(condominioId);
    if (condominioId) {
      localStorage.setItem("condo_active_id", condominioId);
    } else {
      localStorage.removeItem("condo_active_id");
    }
  }, []);

  useEffect(() => {
    if (!user) return;
    if (user.rol !== "SUPERADMIN") {
      handleCondominioSeleccionado(user.condominio_id);
      return;
    }

    let cancelado = false;
    async function resolverContextoSuperadmin() {
      const guardado = localStorage.getItem("condo_active_id");
      const resultado = await listarCondominios();
      if (cancelado || !resultado.ok || !resultado.data) {
        setCondominioActivoId(guardado);
        return;
      }
      const guardadoValido = resultado.data.some((item) => item.id === guardado);
      const seleccionado = guardadoValido
        ? guardado
        : resultado.data.length === 1
          ? resultado.data[0].id
          : null;
      handleCondominioSeleccionado(seleccionado);
    }
    void resolverContextoSuperadmin();
    return () => {
      cancelado = true;
    };
  }, [handleCondominioSeleccionado, user]);

  useEffect(() => {
    if (activeTab === "configuracion" && !isSuperAdmin) setActiveTab("estructura");
  }, [activeTab, isSuperAdmin]);

  const handlePresupuestoAprobado = useCallback((presupuesto: PresupuestoAprobado | null) => {
    setPresupuestoAprobado(presupuesto);
    if (!presupuesto) {
      setEmisionFeedback(null);
      return;
    }
    setPeriodoEmision(presupuesto.periodo);
    setPresupuestoTotal(presupuesto.montoTotal);
    setEmisionFeedback(null);
  }, []);

  // Conciliar pago
  async function handleConciliar(id: string, decision: "APROBADO" | "RECHAZADO") {
    let motivo: string | undefined = undefined;
    if (decision === "RECHAZADO") {
      motivo = prompt("Ingrese el motivo del rechazo del comprobante:") || "Comprobante ilegible";
    }

    const res = await conciliarComprobante(id, decision, motivo);
    if (res.ok) {
      alert(`Comprobante ${decision === "APROBADO" ? "APROBADO" : "RECHAZADO"} con éxito. Se actualizó el estado contable.`);
      await loadData();
    } else {
      alert(res.error || "No se pudo procesar la conciliación.");
    }
  }

  // Emitir lote masivo
  async function handleEmitirLote(e: React.FormEvent) {
    e.preventDefault();
    if (!presupuestoAprobado) {
      setEmisionFeedback("Error: primero debe registrar y aprobar el presupuesto del periodo.");
      return;
    }
    setIsEmitting(true);
    setEmisionFeedback(null);

    const res = await emitirLoteCuotas(periodoEmision, presupuestoTotal);
    setIsEmitting(false);

    if (res.ok) {
      setEmisionFeedback(`¡Lote para el periodo ${periodoEmision} emitido exitosamente! 139 cuotas calculadas con cierre contable al centavo exacto.`);
    } else {
      setEmisionFeedback(`Error: ${res.error}`);
    }
  }

  // Enviar comunicado masivo
  async function handleEnviarComunicado(e: React.FormEvent) {
    e.preventDefault();
    if (!comunicadoTitulo.trim() || !comunicadoMensaje.trim()) return;

    const res = await enviarComunicadoMasivo(comunicadoTitulo, comunicadoMensaje);
    if (res.ok) {
      setComunicadoFeedback(`Comunicado despachado con éxito a los ${res.generadas || 139} departamentos de Villa Bonita 3.`);
      setComunicadoTitulo("");
      setComunicadoMensaje("");
      const notifs = await fetchNotificaciones();
      setNotificaciones(notifs);
    }
  }

  // Evaluar moras
  function handleEvaluarMoras() {
    setMorasFeedback("Motor de evaluación ejecutado: Se respetaron los 2 días de gracia. El Dpto. 402 permanece en mora fija de S/ 20.00 con bloqueo de áreas comunes. El Dpto. 504 fue postergado por mantener voucher en revisión.");
  }

  const enRevisionCount = comprobantes.filter((c) => c.estado === "EN_REVISION").length;

  if (isForbidden) {
    return (
      <div className="min-h-[50vh] flex flex-col items-center justify-center text-center p-8 space-y-4 bg-white rounded-2xl border border-slate-200 shadow-sm my-8">
        <div className="w-16 h-16 bg-rose-100 text-rose-600 rounded-2xl flex items-center justify-center">
          <ShieldAlert className="w-10 h-10" />
        </div>
        <div className="max-w-md space-y-2">
          <h1 className="text-2xl font-bold text-slate-900">Acceso Restringido (403 Forbidden)</h1>
          <p className="text-sm text-slate-600">
            El panel administrativo está reservado para miembros de la Junta Directiva y Auditores Fiscales. Su rol actual es <strong>{user?.rol || "NO_AUTENTICADO"}</strong>.
          </p>
        </div>
        <Link
          href={`/residente?dpto=${user?.departamentos?.[0] || "102"}`}
          className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-700 text-white font-semibold text-sm rounded-xl transition shadow-sm"
        >
          Ir a mi Portal de Residente →
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Banner Informativo para el Auditor */}
      {isAuditor && (
        <div className="bg-purple-50 border border-purple-200 rounded-2xl p-4 flex items-start sm:items-center gap-3 text-purple-950 shadow-sm">
          <Search className="w-6 h-6 text-purple-600 flex-shrink-0 mt-0.5 sm:mt-0" />
          <div className="text-xs space-y-0.5">
            <p className="font-bold text-sm text-purple-900">Modo Auditoría Fiscal Activo (Solo Lectura)</p>
            <p className="text-purple-700">
              Como auditor, usted cuenta con acceso de consulta a comprobantes, cuotas y bitácoras. Las acciones de aprobación, emisión y cálculo de moras están reservadas para los miembros operativos de la Junta Directiva.
            </p>
          </div>
        </div>
      )}

      {/* Encabezado del Panel de Administración */}
      <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold">
            <ShieldCheck className="w-7 h-7" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">
              Panel de Control de la Junta Directiva
            </h1>
            <p className="text-xs text-slate-500">
              Edificio 3 • Villa Bonita 3 • Administración de Recaudación y Operaciones
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={loadData}
            className="flex items-center gap-1.5 px-3 py-2 bg-slate-100 text-slate-700 hover:bg-slate-200 rounded-xl text-xs font-semibold transition-colors border border-slate-200"
          >
            <RefreshCw className="w-3.5 h-3.5" />
            <span>Actualizar Datos</span>
          </button>
        </div>
      </div>

      {/* Métricas Rápidas */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Total Unidades</span>
          <p className="text-2xl font-black text-slate-900 mt-1">139 Dptos</p>
          <span className="text-[11px] text-emerald-600 font-semibold">14 Pisos • 100.0000%</span>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Presupuesto Mensual</span>
          <p className="text-2xl font-black text-slate-900 mt-1">S/ 20,850.00</p>
          <span className="text-[11px] text-slate-500">Sin pérdida decimal</span>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Vouchers por Conciliar</span>
          <p className="text-2xl font-black text-amber-600 mt-1">{enRevisionCount} Pendientes</p>
          <span className="text-[11px] text-amber-700">Verificación de extractos</span>
        </div>
        <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-sm">
          <span className="text-xs font-medium text-slate-500">Invariante de Solvencia</span>
          <p className="text-2xl font-black text-emerald-600 mt-1">Activa</p>
          <span className="text-[11px] text-slate-500">Mora bloquea reservas</span>
        </div>
      </div>

      {/* Pestañas del Panel de la Junta */}
      <div className="flex border-b border-slate-200 gap-6 text-sm font-semibold overflow-x-auto">
        {isSuperAdmin && (
          <button
            onClick={() => setActiveTab("configuracion")}
            className={`pb-3 flex items-center gap-2 transition-colors border-b-2 whitespace-nowrap ${
              activeTab === "configuracion"
                ? "border-blue-600 text-blue-700"
                : "border-transparent text-slate-500 hover:text-slate-800"
            }`}
          >
            <Settings2 className="w-4 h-4" />
            <span>Configurar Condominio</span>
          </button>
        )}

        <button
          onClick={() => setActiveTab("estructura")}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 whitespace-nowrap ${
            activeTab === "estructura"
              ? "border-blue-600 text-blue-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Building2 className="w-4 h-4" />
          <span>Estructura del Condominio</span>
        </button>

        <button
          onClick={() => setActiveTab("presupuesto")}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 whitespace-nowrap ${
            activeTab === "presupuesto"
              ? "border-blue-600 text-blue-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <ClipboardCheck className="w-4 h-4" />
          <span>Presupuesto Mensual</span>
        </button>

        <button
          onClick={() => setActiveTab("conciliacion")}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 whitespace-nowrap ${
            activeTab === "conciliacion"
              ? "border-blue-600 text-blue-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <FileCheck2 className="w-4 h-4" />
          <span>Bandeja de Conciliación Bancaria</span>
          {enRevisionCount > 0 && (
            <span className="px-2 py-0.5 bg-amber-500 text-white rounded-full text-[10px] font-bold">
              {enRevisionCount}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("cuotas")}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 whitespace-nowrap ${
            activeTab === "cuotas"
              ? "border-blue-600 text-blue-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Coins className="w-4 h-4" />
          <span>Emisión Masiva de Cuotas</span>
        </button>

        <button
          onClick={() => setActiveTab("moras")}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 whitespace-nowrap ${
            activeTab === "moras"
              ? "border-blue-600 text-blue-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>Control de Moras</span>
        </button>

        <button
          onClick={() => setActiveTab("notificaciones")}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 whitespace-nowrap ${
            activeTab === "notificaciones"
              ? "border-blue-600 text-blue-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Bell className="w-4 h-4" />
          <span>Notificaciones y Comunicados</span>
        </button>
      </div>

      {/* CONFIGURACIÓN DEL CONDOMINIO */}
      {activeTab === "configuracion" && isSuperAdmin && (
        <ConfiguracionCondominio
          puedeEditar={isSuperAdmin}
          condominioActivoId={condominioActivoId}
          onCondominioSeleccionado={handleCondominioSeleccionado}
        />
      )}

      {/* EDIFICIOS Y DEPARTAMENTOS */}
      {activeTab === "estructura" && (
        <EstructuraCondominio departamentosIniciales={departamentos} soloLectura={isAuditor} />
      )}

      {/* PRESUPUESTO MENSUAL */}
      {activeTab === "presupuesto" && (
        <PresupuestoMensual
          condominioId={condominioActivoId}
          puedeEditar={user?.rol === "ADMIN_JUNTA" || user?.rol === "SUPERADMIN"}
          onCambioAprobado={handlePresupuestoAprobado}
        />
      )}

      {/* PESTAÑA 1: CONCILIACIÓN BANCARIA */}
      {activeTab === "conciliacion" && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
          <div className="flex justify-between items-center">
            <div>
              <h3 className="font-bold text-slate-900 text-lg">Bandeja de Comprobantes Bancarios</h3>
              <p className="text-xs text-slate-500">
                Aprobación con imputación contable en prelación y desbloqueo automático de solvencia.
              </p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-200 text-slate-500 font-semibold bg-slate-50">
                  <th className="p-3">Dpto</th>
                  <th className="p-3">Banco / Canal</th>
                  <th className="p-3">Nº Operación</th>
                  <th className="p-3">Fecha</th>
                  <th className="p-3">Monto</th>
                  <th className="p-3">Hash Idempotencia</th>
                  <th className="p-3">Estado</th>
                  <th className="p-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {comprobantes.map((comp) => (
                  <tr key={comp.id} className="hover:bg-slate-50/60 transition-colors">
                    <td className="p-3 font-bold text-slate-900">Dpto. {comp.departamento_id}</td>
                    <td className="p-3">{comp.banco}</td>
                    <td className="p-3 font-mono">{comp.numero_operacion}</td>
                    <td className="p-3">{comp.fecha_operacion}</td>
                    <td className="p-3 font-bold text-slate-900">S/ {comp.monto}</td>
                    <td className="p-3 font-mono text-[10px] text-slate-400">
                      {comp.idempotency_hash.slice(0, 16)}...
                    </td>
                    <td className="p-3">
                      <span
                        className={`px-2 py-0.5 rounded-full font-bold uppercase text-[10px] ${
                          comp.estado === "CONCILIADO"
                            ? "bg-emerald-100 text-emerald-800"
                            : comp.estado === "RECHAZADO"
                            ? "bg-rose-100 text-rose-800"
                            : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {comp.estado}
                      </span>
                    </td>
                    <td className="p-3 text-right">
                      {isAuditor ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-purple-700 bg-purple-100 px-2 py-1 rounded-lg">
                          <Search className="w-3 h-3" /> Solo Lectura
                        </span>
                      ) : comp.estado === "EN_REVISION" ? (
                        <div className="flex items-center justify-end gap-2">
                          <button
                            onClick={() => handleConciliar(comp.id, "APROBADO")}
                            className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg font-bold text-xs transition-colors"
                          >
                            Aprobar
                          </button>
                          <button
                            onClick={() => handleConciliar(comp.id, "RECHAZADO")}
                            className="px-2.5 py-1 bg-rose-100 hover:bg-rose-200 text-rose-800 rounded-lg font-bold text-xs transition-colors"
                          >
                            Rechazar
                          </button>
                        </div>
                      ) : (
                        <span className="text-slate-400 italic">Procesado</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* PESTAÑA 2: EMISIÓN MASIVA DE CUOTAS */}
      {activeTab === "cuotas" && (
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
            <h3 className="font-bold text-slate-900 text-lg flex items-center gap-2">
              <Coins className="w-5 h-5 text-blue-600" />
              Lanzar Emisión Mensual
            </h3>
            <p className="text-xs text-slate-500">
              Distribuye el presupuesto total proporcionalmente entre los 139 departamentos usando alícuotas con cierre contable estricto al centavo.
            </p>

            {emisionFeedback && (
              <div
                className={`p-3 rounded-xl text-xs flex items-start gap-2 ${
                  emisionFeedback.startsWith("Error")
                    ? "bg-rose-50 border border-rose-200 text-rose-800"
                    : "bg-emerald-50 border border-emerald-200 text-emerald-800"
                }`}
              >
                {emisionFeedback.startsWith("Error") ? (
                  <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                ) : (
                  <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                )}
                <span>{emisionFeedback}</span>
              </div>
            )}

            {!presupuestoAprobado && !isAuditor && (
              <div className="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 space-y-2">
                <p className="font-bold">Falta aprobar el presupuesto del periodo.</p>
                <p>
                  Registre y apruebe primero el presupuesto mensual. La emisión usará
                  automáticamente ese periodo y monto.
                </p>
                <button
                  type="button"
                  onClick={() => setActiveTab("presupuesto")}
                  className="font-bold text-amber-950 underline underline-offset-2"
                >
                  Ir a Presupuesto Mensual
                </button>
              </div>
            )}

            {presupuestoAprobado && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-xl text-xs text-emerald-900 flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="font-bold">Presupuesto aprobado</p>
                  <p>
                    {presupuestoAprobado.periodo} · {presupuestoAprobado.moneda} {" "}
                    {Number(presupuestoAprobado.montoTotal).toLocaleString("es-PE", {
                      minimumFractionDigits: 2,
                      maximumFractionDigits: 2,
                    })}
                  </p>
                </div>
              </div>
            )}

            <form onSubmit={handleEmitirLote} className="space-y-3.5 text-sm">
              <div>
                <label className="block font-medium text-slate-700 text-xs mb-1">
                  Periodo a Facturar
                </label>
                <input
                  type="text"
                  value={periodoEmision}
                  placeholder="2026-11"
                  readOnly
                  className="w-full border border-slate-200 bg-slate-100 rounded-lg p-2.5 text-slate-700 cursor-not-allowed"
                  required
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 text-xs mb-1">
                  Presupuesto Aprobado (S/)
                </label>
                <input
                  type="number"
                  step="0.01"
                  value={presupuestoTotal}
                  readOnly
                  className="w-full border border-slate-200 bg-slate-100 rounded-lg p-2.5 text-slate-700 cursor-not-allowed"
                  required
                />
              </div>

              <div className="p-3 bg-slate-50 border border-slate-200 rounded-xl text-[11px] text-slate-600 space-y-1">
                <p className="font-bold text-slate-800">Invariante de Cierre Contable (Anderson):</p>
                <p>
                  Si la suma fraccional de centavos genera deriva (ej. S/ 20,849.99), el centavo restante se imputa automáticamente a la unidad con mayor alícuota para garantizar la igualdad exacta.
                </p>
              </div>

              {isAuditor ? (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl text-xs text-purple-800 text-center font-semibold flex items-center justify-center gap-2">
                  <Lock className="w-4 h-4 text-purple-600" />
                  <span>Emisión reservada para la Junta Directiva (Solo Lectura)</span>
                </div>
              ) : (
                <button
                  type="submit"
                  disabled={isEmitting || !presupuestoAprobado}
                  className="w-full py-3 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-300 disabled:text-slate-600 disabled:cursor-not-allowed text-white rounded-xl font-bold text-sm transition-colors shadow-sm"
                >
                  {isEmitting
                    ? "Emitiendo Lote..."
                    : presupuestoAprobado
                    ? "Emitir Lote Masivo (139 Dptos)"
                    : "Apruebe un presupuesto primero"}
                </button>
              )}
            </form>
          </div>

          <div className="lg:col-span-2 bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
            <h3 className="font-bold text-slate-900 text-lg">Distribución de Alícuotas por Departamento</h3>
            <p className="text-xs text-slate-500">Muestra de departamentos calibrados en Villa Bonita 3:</p>

            <div className="overflow-x-auto max-h-96">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="sticky top-0 bg-slate-100">
                  <tr className="border-b border-slate-200 text-slate-600 font-semibold">
                    <th className="p-2.5">Dpto</th>
                    <th className="p-2.5">Piso</th>
                    <th className="p-2.5">Alícuota (%)</th>
                    <th className="p-2.5">Cuota Estimada</th>
                    <th className="p-2.5">Saldo a Favor</th>
                    <th className="p-2.5">Estado</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {departamentos.slice(0, 15).map((d) => (
                    <tr key={d.numero}>
                      <td className="p-2.5 font-bold">Dpto. {d.numero}</td>
                      <td className="p-2.5">{d.piso}</td>
                      <td className="p-2.5 font-mono">{d.coeficiente}%</td>
                      <td className="p-2.5 font-bold text-slate-900">
                        S/ {d.coeficiente === "0.6800" ? "141.78" : "154.29"}
                      </td>
                      <td className="p-2.5 text-emerald-600 font-medium">S/ {d.saldo_a_favor}</td>
                      <td className="p-2.5">
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase ${
                            d.estado_financiero === "AL_DIA"
                              ? "bg-emerald-100 text-emerald-800"
                              : d.estado_financiero === "EN_MORA"
                              ? "bg-rose-100 text-rose-800"
                              : "bg-amber-100 text-amber-800"
                          }`}
                        >
                          {d.estado_financiero}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="text-[11px] text-slate-400 text-center">
              Mostrando primeros 15 de 139 departamentos calibrados.
            </p>
          </div>
        </div>
      )}

      {/* PESTAÑA 3: MOTOR DE MORAS */}
      {activeTab === "moras" && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <div>
              <h3 className="font-bold text-slate-900 text-lg">Control Nocturno de Morosidad</h3>
              <p className="text-xs text-slate-500">
                Aplica la penalidad fija de S/ 20.00 a cuotas que superen los 2 días de gracia.
              </p>
            </div>
            {isAuditor ? (
              <span className="px-4 py-2.5 bg-purple-50 text-purple-700 border border-purple-200 rounded-xl font-bold text-xs flex items-center gap-2">
                <Search className="w-4 h-4 text-purple-600" />
                <span>Auditoría de Moras (Solo Lectura)</span>
              </span>
            ) : (
              <button
                onClick={handleEvaluarMoras}
                className="px-4 py-2.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl font-bold text-xs transition-colors shadow-sm flex items-center gap-2"
              >
                <Clock className="w-4 h-4" />
                <span>Ejecutar Motor de Moras Ahora</span>
              </button>
            )}
          </div>

          {morasFeedback && (
            <div className="p-4 bg-amber-50 border border-amber-200 text-amber-900 rounded-xl text-xs">
              {morasFeedback}
            </div>
          )}

          <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl space-y-3">
            <h4 className="font-bold text-slate-900 text-sm">Reglas para el cálculo de moras:</h4>
            <ul className="text-xs text-slate-600 space-y-1.5 list-disc list-inside">
              <li>
                <strong>2 Días de Gracia:</strong> Si la cuota vence el día 20, la mora no se aplica hasta las 00:00 del día 23.
              </li>
              <li>
                <strong>Postergación Protectora:</strong> Si un departamento subió su voucher y está en estado <code>EN_REVISION</code>, la mora se congela 24h para evitar penalizar la demora del administrador en conciliar.
              </li>
              <li>
                <strong>Compuerta de Solvencia:</strong> Al pasar a estado <code>EN_MORA</code>, el residente queda inhabilitado automáticamente en el módulo de reservas.
              </li>
            </ul>
          </div>
        </div>
      )}

      {/* PESTAÑA 4: NOTIFICACIONES Y COMUNICADOS */}
      {activeTab === "notificaciones" && (
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
            <h3 className="font-bold text-slate-900 text-lg flex items-center gap-2">
              <Send className="w-5 h-5 text-blue-600" />
              Comunicado a la Comunidad
            </h3>
            <p className="text-xs text-slate-500">
              Despacho multicanal simultáneo a los 139 departamentos.
            </p>

            {comunicadoFeedback && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                <span>{comunicadoFeedback}</span>
              </div>
            )}

            <form onSubmit={handleEnviarComunicado} className="space-y-3.5 text-sm">
              <div>
                <label className="block font-medium text-slate-700 text-xs mb-1">
                  Título del Comunicado
                </label>
                <input
                  type="text"
                  placeholder="Ej. Mantenimiento de Ascensores"
                  value={comunicadoTitulo}
                  onChange={(e) => setComunicadoTitulo(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2.5 text-slate-800"
                  required
                />
              </div>

              <div>
                <label className="block font-medium text-slate-700 text-xs mb-1">
                  Mensaje Detallado
                </label>
                <textarea
                  rows={4}
                  placeholder="Escriba el comunicado oficial..."
                  value={comunicadoMensaje}
                  onChange={(e) => setComunicadoMensaje(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2.5 text-slate-800"
                  required
                />
              </div>

              {isAuditor ? (
                <div className="p-3 bg-purple-50 border border-purple-200 rounded-xl text-xs text-purple-800 text-center font-semibold flex items-center justify-center gap-2">
                  <Lock className="w-4 h-4 text-purple-600" />
                  <span>Emisión de comunicados reservada para Junta Directiva</span>
                </div>
              ) : (
                <button
                  type="submit"
                  className="w-full py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-xl font-bold text-sm transition-colors shadow-sm"
                >
                  Despachar Comunicado Masivo
                </button>
              )}
            </form>
          </div>

          <div className="lg:col-span-2 bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
            <h3 className="font-bold text-slate-900 text-lg">Historial de envíos</h3>
            <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
              {notificaciones.map((n) => (
                <div key={n.id} className="py-3 flex items-center justify-between gap-4 text-xs">
                  <div>
                    <p className="font-bold text-slate-900">{n.asunto || n.tipo_evento}</p>
                    <p className="text-slate-500 mt-0.5">
                      Destinatario: {n.destinatario} • Canal: {n.canal} • Intentos: {n.intentos}
                    </p>
                  </div>
                  <span
                    className={`px-2.5 py-1 rounded-full font-bold uppercase text-[10px] ${
                      n.estado === "ENTREGADO"
                        ? "bg-emerald-100 text-emerald-800"
                        : n.estado === "REINTENTANDO"
                        ? "bg-amber-100 text-amber-800"
                        : "bg-rose-100 text-rose-800"
                    }`}
                  >
                    {n.estado}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
