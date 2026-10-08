import Link from "next/link";
import {
  Building,
  CreditCard,
  CalendarCheck2,
  BellRing,
  ArrowRight,
  ShieldAlert,
  CheckCircle2,
  Users,
  Coins,
  History,
} from "lucide-react";

export default function Home() {
  return (
    <div className="space-y-8 py-4">
      {/* Hero Banner */}
      <div className="bg-gradient-to-br from-slate-900 via-slate-800 to-indigo-950 text-white rounded-2xl p-6 sm:p-10 shadow-xl relative overflow-hidden">
        <div className="absolute right-0 top-0 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none"></div>
        <div className="max-w-3xl space-y-4 relative z-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/20 text-emerald-300 text-xs font-semibold border border-emerald-500/30">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            <span>Sistema Piloto en Producción: Edificio 3 (139 Departamentos)</span>
          </div>
          <h1 className="text-3xl sm:text-5xl font-black tracking-tight leading-tight">
            Automatización Total para tu Condominio con Rigor Contable
          </h1>
          <p className="text-slate-300 text-sm sm:text-base leading-relaxed">
            CondoManager sustituye hojas de Excel y validaciones manuales por un motor guiado por eventos,
            cálculos monetarios precisos, conciliación bancaria y control de solvencia para áreas comunes.
          </p>
        </div>

        {/* Métricas clave */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-8 pt-6 border-t border-slate-700/60">
          <div>
            <span className="text-xs text-slate-400">Total Unidades</span>
            <p className="text-2xl font-bold text-white flex items-center gap-1.5 mt-0.5">
              <Users className="w-5 h-5 text-indigo-400" />
              139 Dptos
            </p>
            <span className="text-[11px] text-emerald-400 font-medium">100.0000% Alícuota</span>
          </div>
          <div>
            <span className="text-xs text-slate-400">Presupuesto Mensual</span>
            <p className="text-2xl font-bold text-white flex items-center gap-1.5 mt-0.5">
              <Coins className="w-5 h-5 text-amber-400" />
              S/ 20,850
            </p>
            <span className="text-[11px] text-slate-400">Cuota base ~S/ 141.78</span>
          </div>
          <div>
            <span className="text-xs text-slate-400">Áreas Comunes</span>
            <p className="text-2xl font-bold text-white flex items-center gap-1.5 mt-0.5">
              <CalendarCheck2 className="w-5 h-5 text-emerald-400" />
              4 Espacios
            </p>
            <span className="text-[11px] text-slate-400">Parrillas, Salón, Gym</span>
          </div>
          <div>
            <span className="text-xs text-slate-400">Invariante de Solvencia</span>
            <p className="text-2xl font-bold text-emerald-400 flex items-center gap-1.5 mt-0.5">
              <ShieldAlert className="w-5 h-5 text-emerald-400" />
              Activa (403)
            </p>
            <span className="text-[11px] text-slate-400">Bloqueo estricto por mora</span>
          </div>
        </div>
      </div>

      {/* Selector de Portales */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Tarjeta Portal Residente */}
        <div className="bg-white rounded-2xl p-6 sm:p-8 shadow-sm border border-slate-200 hover:shadow-md transition-all flex flex-col justify-between group">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-emerald-100 text-emerald-700 flex items-center justify-center font-bold">
              <CreditCard className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-slate-900 group-hover:text-emerald-700 transition-colors">
                Portal de Residentes
              </h2>
              <p className="text-slate-600 text-sm mt-1 leading-relaxed">
                Diseñado para propietarios e inquilinos desde el celular o computadora.
              </p>
            </div>
            <ul className="space-y-2.5 text-sm text-slate-700 pt-2">
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>Consulta de estado de cuenta y cuotas vigentes</span>
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>Reporte de pagos (Yape, Plin, Transferencias BCP/Interbank)</span>
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
                <span>Reserva de parrillas y salones con compuerta de solvencia</span>
              </li>
            </ul>
          </div>

          <div className="pt-6 mt-6 border-t border-slate-100">
            <Link
              href="/residente"
              className="inline-flex items-center justify-center gap-2 w-full px-5 py-3 rounded-xl bg-emerald-600 text-white font-semibold text-sm hover:bg-emerald-700 transition-colors shadow-sm"
            >
              <span>Ingresar como Residente</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Tarjeta Portal Junta Directiva */}
        <div className="bg-white rounded-2xl p-6 sm:p-8 shadow-sm border border-slate-200 hover:shadow-md transition-all flex flex-col justify-between group">
          <div className="space-y-4">
            <div className="w-12 h-12 rounded-xl bg-blue-100 text-blue-700 flex items-center justify-center font-bold">
              <Building className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-2xl font-bold text-slate-900 group-hover:text-blue-700 transition-colors">
                Junta Directiva y Administración
              </h2>
              <p className="text-slate-600 text-sm mt-1 leading-relaxed">
                Panel integral de control operativo, contable y auditoría inmutable.
              </p>
            </div>
            <ul className="space-y-2.5 text-sm text-slate-700 pt-2">
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <span>Emisión masiva mensual de cuotas para los 139 departamentos</span>
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <span>Bandeja de conciliación bancaria y prevención de vouchers duplicados</span>
              </li>
              <li className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-blue-600 flex-shrink-0" />
                <span>Motor de moras (S/ 20.00) tras 2 días de gracia y bitácora de auditoría</span>
              </li>
            </ul>
          </div>

          <div className="pt-6 mt-6 border-t border-slate-100">
            <Link
              href="/junta"
              className="inline-flex items-center justify-center gap-2 w-full px-5 py-3 rounded-xl bg-blue-600 text-white font-semibold text-sm hover:bg-blue-700 transition-colors shadow-sm"
            >
              <span>Ingresar como Administrador</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>

      {/* Banner explicativo de reglas automáticas */}
      <div className="bg-slate-100 border border-slate-200 rounded-xl p-5 sm:p-6 text-sm text-slate-700 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div className="space-y-1">
          <p className="font-bold text-slate-900 flex items-center gap-2">
            <History className="w-4 h-4 text-indigo-600" />
            Demostración de reglas automáticas del sistema
          </p>
          <p className="text-slate-600 text-xs sm:text-sm">
            Prueba cambiar entre el <strong>Dpto. 102</strong> (Al Día / Solvente) y el <strong>Dpto. 402</strong> (En Mora). Verás cómo el sistema bloquea inmediatamente las reservas de parrilla aplicando la regla matemática del Dominio 04.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            href="/residente?dpto=102"
            className="px-3 py-1.5 bg-emerald-100 text-emerald-800 font-semibold text-xs rounded-lg hover:bg-emerald-200 transition-colors border border-emerald-300"
          >
            Probar Dpto. 102 (Solvente)
          </Link>
          <Link
            href="/residente?dpto=402"
            className="px-3 py-1.5 bg-rose-100 text-rose-800 font-semibold text-xs rounded-lg hover:bg-rose-200 transition-colors border border-rose-300"
          >
            Probar Dpto. 402 (Moroso)
          </Link>
        </div>
      </div>
    </div>
  );
}
