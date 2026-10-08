"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import {
  AreaComun,
  Departamento,
  Reserva,
  ComprobantePago,
  fetchAreasComunes,
  fetchDepartamentos,
  fetchReservas,
  crearReserva,
  cancelarReserva,
  reportarPago,
  fetchComprobantes,
} from "@/lib/api";
import {
  ShieldAlert,
  ShieldCheck,
  Calendar,
  CreditCard,
  Clock,
  Coins,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  PlusCircle,
  Building,
  User,
  Search,
  Lock,
} from "lucide-react";

function ResidenteContent() {
  const searchParams = useSearchParams();
  const dptoParam = searchParams.get("dpto");
  const { user, activeDepartment, setActiveDepartment } = useAuth();

  const [departamentoNumero, setDepartamentoNumero] = useState(
    dptoParam || activeDepartment || "102"
  );
  const [departamentos, setDepartamentos] = useState<Departamento[]>([]);
  const [activeTab, setActiveTab] = useState<"reservas" | "pagos" | "cuenta">("reservas");

  const [areas, setAreas] = useState<AreaComun[]>([]);
  const [reservas, setReservas] = useState<Reserva[]>([]);
  const [comprobantes, setComprobantes] = useState<ComprobantePago[]>([]);

  // Estado del Formulario de Reserva
  const [selectedAreaId, setSelectedAreaId] = useState<string>("");
  const [fechaReserva, setFechaReserva] = useState<string>("2026-10-25");
  const [horaInicio, setHoraInicio] = useState<string>("19:00");
  const [horaFin, setHoraFin] = useState<string>("22:00");
  const [reservaError, setReservaError] = useState<string | null>(null);
  const [reservaSuccess, setReservaSuccess] = useState<string | null>(null);
  const [isSubmittingReserva, setIsSubmittingReserva] = useState<boolean>(false);

  // Estado del Formulario de Reporte de Pago
  const [banco, setBanco] = useState<string>("YAPE");
  const [numeroOperacion, setNumeroOperacion] = useState<string>("");
  const [montoPago, setMontoPago] = useState<string>("150.00");
  const [fechaOperacion, setFechaOperacion] = useState<string>("2026-10-20");
  const [pagoError, setPagoError] = useState<string | null>(null);
  const [pagoSuccess, setPagoSuccess] = useState<string | null>(null);

  // Carga inicial
  useEffect(() => {
    async function initData() {
      const [deptosData, areasData, reservasData, compsData] = await Promise.all([
        fetchDepartamentos(),
        fetchAreasComunes(),
        fetchReservas(),
        fetchComprobantes(),
      ]);
      setDepartamentos(deptosData);
      setAreas(areasData);
      if (areasData.length > 0) setSelectedAreaId(areasData[0].id);
      setReservas(reservasData);
      setComprobantes(compsData);
    }
    initData();
  }, []);

  useEffect(() => {
    if (dptoParam) setDepartamentoNumero(dptoParam);
  }, [dptoParam]);

  const deptoActual =
    departamentos.find((d) => d.numero === departamentoNumero) || {
      numero: departamentoNumero,
      piso: 1,
      coeficiente: "0.6800",
      saldo_a_favor: "0.00",
      estado_financiero: "AL_DIA" as const,
      deuda_vencida: "0.00",
    };

  const estaEnMora = deptoActual.estado_financiero === "EN_MORA";

  // Manejar reserva
  async function handleCrearReserva(e: React.FormEvent) {
    e.preventDefault();
    setReservaError(null);
    setReservaSuccess(null);
    setIsSubmittingReserva(true);

    const res = await crearReserva({
      condominio_id: "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      area_id: selectedAreaId,
      departamento_id: departamentoNumero,
      fecha_reserva: fechaReserva,
      hora_inicio: horaInicio,
      hora_fin: horaFin,
    });

    setIsSubmittingReserva(false);
    if (res.ok) {
      setReservaSuccess("¡Reserva confirmada con éxito! Se ha notificado a su correo con las normas del espacio.");
      const updatedReservas = await fetchReservas();
      setReservas(updatedReservas);
    } else {
      setReservaError(res.error || "No se pudo registrar la reserva.");
    }
  }

  // Cancelar reserva
  async function handleCancelar(id: string) {
    if (!confirm("¿Desea cancelar esta reserva? Se liberará el turno para otros residentes.")) return;
    const res = await cancelarReserva(id);
    if (res.ok) {
      const updated = await fetchReservas();
      setReservas(updated);
    } else {
      alert(res.error || "No fue posible cancelar la reserva.");
    }
  }

  // Manejar reporte de pago
  async function handleReportarPago(e: React.FormEvent) {
    e.preventDefault();
    setPagoError(null);
    setPagoSuccess(null);

    if (!numeroOperacion.trim()) {
      setPagoError("Ingrese el número de operación bancaria.");
      return;
    }

    const res = await reportarPago({
      departamento_id: departamentoNumero,
      banco,
      numero_operacion: numeroOperacion.trim(),
      fecha_operacion: fechaOperacion,
      monto: montoPago,
    });

    if (res.ok) {
      setPagoSuccess(`Comprobante registrado en revisión. Clave SHA-256 calculada.`);
      setNumeroOperacion("");
      const comps = await fetchComprobantes();
      setComprobantes(comps);
    } else {
      setPagoError(res.error || "Error al reportar pago.");
    }
  }

  return (
    <div className="space-y-6">
      {/* Selector de Departamento de Prueba y Bienvenida */}
      <div className="bg-white rounded-2xl p-5 shadow-sm border border-slate-200 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-emerald-600 text-white flex items-center justify-center font-bold">
            <Building className="w-5 h-5" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">
              Portal del Residente • Dpto. {deptoActual.numero}
            </h1>
            <p className="text-xs text-slate-500">
              Piso {deptoActual.piso} • Alícuota: {deptoActual.coeficiente}% • Villa Bonita 3
            </p>
          </div>
        </div>

        {/* Switcher contextual según rol */}
        {user?.rol === "ADMIN_JUNTA" || user?.rol === "SUPERADMIN" ? (
          <div className="flex items-center gap-2 bg-slate-100 p-1.5 rounded-xl border border-slate-200 text-xs">
            <span className="font-semibold text-slate-600 px-2 flex items-center gap-1">
              <Search className="w-3.5 h-3.5 text-blue-600" />
              Soporte Junta:
            </span>
            <button
              onClick={() => {
                setDepartamentoNumero("102");
                setActiveDepartment("102");
              }}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                departamentoNumero === "102"
                  ? "bg-emerald-600 text-white shadow-xs"
                  : "text-slate-700 hover:bg-white"
              }`}
            >
              102 (Al Día)
            </button>
            <button
              onClick={() => {
                setDepartamentoNumero("302");
                setActiveDepartment("302");
              }}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                departamentoNumero === "302"
                  ? "bg-emerald-600 text-white shadow-xs"
                  : "text-slate-700 hover:bg-white"
              }`}
            >
              302 (Saldo +)
            </button>
            <button
              onClick={() => {
                setDepartamentoNumero("402");
                setActiveDepartment("402");
              }}
              className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                departamentoNumero === "402"
                  ? "bg-rose-600 text-white shadow-xs"
                  : "text-rose-700 hover:bg-rose-100"
              }`}
            >
              402 (En Mora)
            </button>
          </div>
        ) : user?.rol === "INQUILINO" ? (
          <div className="flex items-center gap-2 bg-teal-50 px-3 py-1.5 rounded-xl border border-teal-200 text-xs text-teal-800 font-semibold">
            <User className="w-4 h-4 text-teal-600" />
            <span>Arrendatario Registrado • Dpto. {deptoActual.numero}</span>
          </div>
        ) : user?.rol === "AUDITOR" ? (
          <div className="flex items-center gap-2 bg-purple-50 px-3 py-1.5 rounded-xl border border-purple-200 text-xs text-purple-800 font-semibold">
            <Search className="w-4 h-4 text-purple-600" />
            <span>Vista de Auditoría • Dpto. {deptoActual.numero}</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 bg-emerald-50 px-3 py-1.5 rounded-xl border border-emerald-200 text-xs text-emerald-800 font-semibold">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Propietario Titular • Dpto. {deptoActual.numero}</span>
          </div>
        )}
      </div>

      {/* Tarjeta de Estado Financiero y Solvencia */}
      <div
        className={`rounded-2xl p-6 border shadow-sm transition-all ${
          estaEnMora
            ? "bg-gradient-to-r from-rose-50 to-rose-100/60 border-rose-200"
            : "bg-gradient-to-r from-emerald-50 to-teal-50/60 border-emerald-200"
        }`}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start gap-4">
            <div
              className={`p-3 rounded-xl mt-0.5 ${
                estaEnMora ? "bg-rose-600 text-white" : "bg-emerald-600 text-white"
              }`}
            >
              {estaEnMora ? <ShieldAlert className="w-7 h-7" /> : <ShieldCheck className="w-7 h-7" />}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span
                  className={`text-xs font-bold px-2.5 py-0.5 rounded-full uppercase tracking-wider ${
                    estaEnMora
                      ? "bg-rose-200 text-rose-900 border border-rose-300"
                      : "bg-emerald-200 text-emerald-900 border border-emerald-300"
                  }`}
                >
                  {estaEnMora ? "Bloqueado por Mora" : "Solvente y al Día"}
                </span>
              </div>
              <h2 className="text-xl font-bold text-slate-900 mt-1">
                {estaEnMora
                  ? "Acceso a Áreas Comunes Temporalmente Suspendido"
                  : "Estado Financiero Óptimo • Habilitado para Reservas"}
              </h2>
              <p className="text-sm text-slate-600 mt-1 max-w-xl">
                {estaEnMora
                  ? `Su departamento registra S/ ${deptoActual.deuda_vencida || "170.00"} en cuotas vencidas. Conforme a la invariante SDD PROC-04, no podrá reservar áreas comunes hasta cancelar su deuda.`
                  : "No registra penalidades ni deudas vencidas pendientes. Puede reservar parrillas y salones con total normalidad."}
              </p>
            </div>
          </div>

          <div className="flex sm:flex-col items-center sm:items-end justify-between border-t sm:border-t-0 pt-3 sm:pt-0 border-slate-200">
            <span className="text-xs text-slate-500">
              {estaEnMora ? "Deuda Vencida Exigible" : "Saldo a Favor Acumulado"}
            </span>
            <p
              className={`text-2xl font-black ${
                estaEnMora ? "text-rose-600" : "text-emerald-700"
              }`}
            >
              S/ {estaEnMora ? deptoActual.deuda_vencida || "170.00" : deptoActual.saldo_a_favor}
            </p>
          </div>
        </div>
      </div>

      {/* Pestañas de Navegación del Residente */}
      <div className="flex border-b border-slate-200 gap-6 text-sm font-semibold">
        <button
          onClick={() => setActiveTab("reservas")}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 ${
            activeTab === "reservas"
              ? "border-emerald-600 text-emerald-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Calendar className="w-4 h-4" />
          <span>Reservas de Áreas Comunes</span>
        </button>

        <button
          onClick={() => setActiveTab("pagos")}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 ${
            activeTab === "pagos"
              ? "border-emerald-600 text-emerald-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <CreditCard className="w-4 h-4" />
          <span>Reportar Comprobante de Pago</span>
        </button>

        <button
          onClick={() => setActiveTab("cuenta")}
          className={`pb-3 flex items-center gap-2 transition-colors border-b-2 ${
            activeTab === "cuenta"
              ? "border-emerald-600 text-emerald-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Coins className="w-4 h-4" />
          <span>Estado de Cuenta</span>
        </button>
      </div>

      {/* CONTENIDO 1: RESERVAS Y CONTROL DE SOLVENCIA */}
      {activeTab === "reservas" && (
        <div className="grid lg:grid-cols-3 gap-6">
          {/* Formulario de Reserva */}
          <div className="lg:col-span-1 bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
            <h3 className="font-bold text-slate-900 text-lg flex items-center gap-2">
              <PlusCircle className="w-5 h-5 text-emerald-600" />
              Solicitar Turno
            </h3>

            {reservaError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                <span>{reservaError}</span>
              </div>
            )}

            {reservaSuccess && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                <span>{reservaSuccess}</span>
              </div>
            )}

            <form onSubmit={handleCrearReserva} className="space-y-3.5 text-sm">
              <div>
                <label className="block font-medium text-slate-700 text-xs mb-1">
                  Espacio Común
                </label>
                <select
                  value={selectedAreaId}
                  onChange={(e) => setSelectedAreaId(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2.5 text-slate-800 bg-white focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
                >
                  {areas.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.nombre} (S/ {a.costo_reserva})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block font-medium text-slate-700 text-xs mb-1">
                  Fecha de Reserva
                </label>
                <input
                  type="date"
                  value={fechaReserva}
                  onChange={(e) => setFechaReserva(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2.5 text-slate-800 focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
                  required
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 text-xs mb-1">
                    Hora Inicio
                  </label>
                  <input
                    type="time"
                    value={horaInicio}
                    onChange={(e) => setHoraInicio(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-slate-800 focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
                    required
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 text-xs mb-1">
                    Hora Fin
                  </label>
                  <input
                    type="time"
                    value={horaFin}
                    onChange={(e) => setHoraFin(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-slate-800 focus:ring-2 focus:ring-emerald-500 focus:outline-hidden"
                    required
                  />
                </div>
              </div>

              {/* Botón con Bloqueo Estricto de Solvencia */}
              <div className="pt-2">
                {estaEnMora ? (
                  <div className="p-3 bg-rose-50 border border-rose-200 rounded-xl space-y-2">
                    <p className="text-xs text-rose-800 font-semibold flex items-center gap-1.5">
                      <ShieldAlert className="w-4 h-4 text-rose-600" />
                      Invariante PROC-04 Activada
                    </p>
                    <p className="text-[11px] text-rose-700 leading-snug">
                      Botón inhabilitado: Su departamento mantiene mora. Debe regularizar su estado de cuenta para desbloquear reservas.
                    </p>
                    <button
                      type="button"
                      disabled
                      className="w-full py-2.5 bg-slate-300 text-slate-500 rounded-xl font-bold text-xs cursor-not-allowed"
                    >
                      Reservas Bloqueadas por Mora
                    </button>
                  </div>
                ) : (
                  <button
                    type="submit"
                    disabled={isSubmittingReserva}
                    className="w-full py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold text-sm transition-colors shadow-sm"
                  >
                    {isSubmittingReserva ? "Verificando..." : "Confirmar Reserva"}
                  </button>
                )}
              </div>
            </form>
          </div>

          {/* Catálogo de Áreas y Reservas Confirmadas */}
          <div className="lg:col-span-2 space-y-6">
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
              <h3 className="font-bold text-slate-900 text-lg">Catálogo de Espacios Disponibles</h3>
              <div className="grid sm:grid-cols-2 gap-4">
                {areas.map((area) => (
                  <div
                    key={area.id}
                    className="p-4 rounded-xl border border-slate-200 hover:border-emerald-300 transition-all bg-slate-50/50"
                  >
                    <div className="flex justify-between items-start">
                      <h4 className="font-bold text-slate-900 text-sm">{area.nombre}</h4>
                      <span className="text-xs font-bold text-emerald-700 bg-emerald-100 px-2 py-0.5 rounded-full">
                        S/ {area.costo_reserva}
                      </span>
                    </div>
                    <p className="text-xs text-slate-600 mt-1">{area.descripcion}</p>
                    <div className="mt-3 text-[11px] text-slate-500 flex items-center gap-3">
                      <span>Aforo: {area.aforo_maximo} personas</span>
                      <span className="text-emerald-600 font-semibold">• Activa</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Listado de Reservas del Condominio */}
            <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
              <h3 className="font-bold text-slate-900 text-lg">Calendario y Turnos Confirmados</h3>
              {reservas.length === 0 ? (
                <p className="text-xs text-slate-500 py-4 text-center">No hay reservas registradas.</p>
              ) : (
                <div className="divide-y divide-slate-100">
                  {reservas.map((r) => (
                    <div key={r.id} className="py-3 flex items-center justify-between gap-4 text-xs">
                      <div>
                        <p className="font-bold text-slate-900">
                          {r.area_nombre || "Área Común"} • Dpto. {r.departamento_id}
                        </p>
                        <p className="text-slate-500 mt-0.5">
                          {r.fecha_reserva} de {r.hora_inicio} a {r.hora_fin} • Tarifa: S/ {r.costo_reserva}
                        </p>
                      </div>

                      <div className="flex items-center gap-3">
                        <span
                          className={`px-2.5 py-1 rounded-full font-bold uppercase ${
                            r.estado === "CONFIRMADA"
                              ? "bg-emerald-100 text-emerald-800"
                              : "bg-slate-100 text-slate-600"
                          }`}
                        >
                          {r.estado}
                        </span>

                        {r.departamento_id === departamentoNumero && r.estado === "CONFIRMADA" && (
                          <button
                            onClick={() => handleCancelar(r.id)}
                            className="text-rose-600 hover:text-rose-800 font-semibold"
                          >
                            Cancelar
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* CONTENIDO 2: REPORTE DE PAGOS E IDEMPOTENCIA */}
      {activeTab === "pagos" && (
        <div className="grid lg:grid-cols-3 gap-6">
          <div className="lg:col-span-1 bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
            <h3 className="font-bold text-slate-900 text-lg flex items-center gap-2">
              <CreditCard className="w-5 h-5 text-emerald-600" />
              Reportar Comprobante
            </h3>

            {pagoError && (
              <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 rounded-xl text-xs flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-rose-600 flex-shrink-0 mt-0.5" />
                <span>{pagoError}</span>
              </div>
            )}

            {pagoSuccess && (
              <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 rounded-xl text-xs flex items-start gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                <span>{pagoSuccess}</span>
              </div>
            )}

            <form onSubmit={handleReportarPago} className="space-y-3.5 text-sm">
              <div>
                <label className="block font-medium text-slate-700 text-xs mb-1">
                  Canal / Banco de Pago
                </label>
                <select
                  value={banco}
                  onChange={(e) => setBanco(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2.5 text-slate-800 bg-white"
                >
                  <option value="YAPE">Yape</option>
                  <option value="PLIN">Plin</option>
                  <option value="BCP">BCP Transferencia / Depósito</option>
                  <option value="INTERBANK">Interbank</option>
                  <option value="BBVA">BBVA</option>
                </select>
              </div>

              <div>
                <label className="block font-medium text-slate-700 text-xs mb-1">
                  Número de Operación Bancaria
                </label>
                <input
                  type="text"
                  placeholder="Ej. 0089214"
                  value={numeroOperacion}
                  onChange={(e) => setNumeroOperacion(e.target.value)}
                  className="w-full border border-slate-300 rounded-lg p-2.5 text-slate-800"
                  required
                />
                <span className="text-[11px] text-slate-400">
                  Se calculará la firma SHA-256 para evitar duplicidad de vouchers.
                </span>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-medium text-slate-700 text-xs mb-1">
                    Monto (S/)
                  </label>
                  <input
                    type="number"
                    step="0.01"
                    value={montoPago}
                    onChange={(e) => setMontoPago(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-slate-800"
                    required
                  />
                </div>
                <div>
                  <label className="block font-medium text-slate-700 text-xs mb-1">
                    Fecha Operación
                  </label>
                  <input
                    type="date"
                    value={fechaOperacion}
                    onChange={(e) => setFechaOperacion(e.target.value)}
                    className="w-full border border-slate-300 rounded-lg p-2.5 text-slate-800"
                    required
                  />
                </div>
              </div>

              <button
                type="submit"
                className="w-full py-3 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl font-bold text-sm transition-colors shadow-sm mt-2"
              >
                Enviar Comprobante a Revisión
              </button>
            </form>
          </div>

          <div className="lg:col-span-2 bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
            <h3 className="font-bold text-slate-900 text-lg">Historial de Comprobantes Enviados</h3>
            <div className="divide-y divide-slate-100">
              {comprobantes
                .filter((c) => c.departamento_id === departamentoNumero)
                .map((comp) => (
                  <div key={comp.id} className="py-3 flex items-center justify-between gap-4 text-xs">
                    <div>
                      <p className="font-bold text-slate-900">
                        {comp.banco} • Op. {comp.numero_operacion} (S/ {comp.monto})
                      </p>
                      <p className="text-slate-500 mt-0.5">Fecha: {comp.fecha_operacion}</p>
                    </div>
                    <span
                      className={`px-2.5 py-1 rounded-full font-bold uppercase ${
                        comp.estado === "CONCILIADO"
                          ? "bg-emerald-100 text-emerald-800"
                          : comp.estado === "RECHAZADO"
                          ? "bg-rose-100 text-rose-800"
                          : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {comp.estado}
                    </span>
                  </div>
                ))}
              {comprobantes.filter((c) => c.departamento_id === departamentoNumero).length === 0 && (
                <p className="text-xs text-slate-500 py-6 text-center">
                  No ha reportado comprobantes recientemente para este departamento.
                </p>
              )}
            </div>
          </div>
        </div>
      )}

      {/* CONTENIDO 3: ESTADO DE CUENTA */}
      {activeTab === "cuenta" && (
        <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-200 space-y-4">
          <h3 className="font-bold text-slate-900 text-lg">Resumen de Cuotas y Obligaciones</h3>
          <div className="grid sm:grid-cols-3 gap-4 pt-2">
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-xs text-slate-500">Cuota Ordinaria Base</span>
              <p className="text-xl font-bold text-slate-900 mt-1">
                S/ {deptoActual.coeficiente === "0.6800" ? "141.78" : "154.29"}
              </p>
              <span className="text-[11px] text-slate-500">Periodo 2026-10</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-xs text-slate-500">Saldo a Favor Aplicable</span>
              <p className="text-xl font-bold text-emerald-700 mt-1">
                S/ {deptoActual.saldo_a_favor}
              </p>
              <span className="text-[11px] text-emerald-600">Amortización automática mensual</span>
            </div>
            <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
              <span className="text-xs text-slate-500">Penalidades por Mora</span>
              <p
                className={`text-xl font-bold mt-1 ${
                  estaEnMora ? "text-rose-600" : "text-slate-900"
                }`}
              >
                S/ {estaEnMora ? "20.00" : "0.00"}
              </p>
              <span className="text-[11px] text-slate-500">
                {estaEnMora ? "Recargo aplicado tras 2 días de gracia" : "Sin moras pendientes"}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function ResidentePage() {
  return (
    <Suspense fallback={<div className="p-8 text-center text-slate-500 font-medium">Cargando Portal de Residentes...</div>}>
      <ResidenteContent />
    </Suspense>
  );
}
