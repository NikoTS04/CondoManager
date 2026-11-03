import { useMemo, useState } from "react";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { VoucherDownloadButton } from "@/components/domain/VoucherDownloadButton";
import { ComprobanteStatusChip } from "@/components/domain/ComprobanteStatusChip";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import type { ComprobantePago, DepartamentoRegistrado } from "@/lib/api";
import { formatDate } from "@/lib/format";

interface ConciliacionSectionProps {
  loading: boolean;
  comprobantes: ComprobantePago[];
  departamentos: DepartamentoRegistrado[];
  isAuditor: boolean;
  onDecide: (id: string, decision: "APROBADO" | "RECHAZADO" | "OBSERVADO") => void;
}

export function ConciliacionSection({
  loading,
  comprobantes,
  departamentos,
  isAuditor,
  onDecide,
}: ConciliacionSectionProps) {
  const [filtroEstado, setFiltroEstado] = useState<string>("TODOS");
  const [filtroDepartamento, setFiltroDepartamento] = useState<string>("TODOS");
  const [filtroBanco, setFiltroBanco] = useState<string>("");
  const [filtroFechaDesde, setFiltroFechaDesde] = useState<string>("");
  const [filtroFechaHasta, setFiltroFechaHasta] = useState<string>("");

  const limpiarFiltros = () => {
    setFiltroEstado("TODOS");
    setFiltroDepartamento("TODOS");
    setFiltroBanco("");
    setFiltroFechaDesde("");
    setFiltroFechaHasta("");
  };

  const hayFiltrosActivos =
    filtroEstado !== "TODOS" ||
    filtroDepartamento !== "TODOS" ||
    filtroBanco.trim() !== "" ||
    filtroFechaDesde !== "" ||
    filtroFechaHasta !== "";

  const bancosDisponibles = useMemo(() => {
    const setBancos = new Set<string>();
    for (const c of comprobantes) {
      if (c.banco) setBancos.add(c.banco);
    }
    return Array.from(setBancos).sort();
  }, [comprobantes]);

  const comprobantesFiltrados = useMemo(() => {
    return comprobantes.filter((c) => {
      if (filtroEstado !== "TODOS" && c.estado !== filtroEstado) {
        return false;
      }
      if (filtroDepartamento !== "TODOS" && c.departamento_id !== filtroDepartamento) {
        return false;
      }
      if (
        filtroBanco.trim() &&
        !c.banco.toLowerCase().includes(filtroBanco.trim().toLowerCase())
      ) {
        return false;
      }
      if (filtroFechaDesde && c.fecha_operacion < filtroFechaDesde) {
        return false;
      }
      if (filtroFechaHasta && c.fecha_operacion > filtroFechaHasta) {
        return false;
      }
      return true;
    });
  }, [comprobantes, filtroEstado, filtroDepartamento, filtroBanco, filtroFechaDesde, filtroFechaHasta]);

  if (loading) return <SkeletonList rows={5} label="Cargando comprobantes" />;

  if (comprobantes.length === 0) {
    return (
      <EmptyState
        title="No hay comprobantes"
        description="Los comprobantes recibidos aparecerán aquí para su conciliación."
      />
    );
  }

  return (
    <Card>
      <CardHeader
        title="Bandeja de conciliación"
        description="Filtra y revisa los comprobantes bancarios antes de aprobarlos, observarlos o rechazarlos."
      />
      <CardBody>
        {/* Barra de Filtros Combinables (CON-24) */}
        <div className="mb-6 rounded-lg border border-line bg-surface-subtle p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">
              Filtros de búsqueda
            </span>
            {hayFiltrosActivos && (
              <button
                type="button"
                onClick={limpiarFiltros}
                className="text-xs font-medium text-accent hover:underline"
              >
                Limpiar filtros
              </button>
            )}
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <div>
              <label htmlFor="filtro-estado" className="mb-1 block text-xs font-medium text-muted">
                Estado
              </label>
              <select
                id="filtro-estado"
                value={filtroEstado}
                onChange={(e) => setFiltroEstado(e.target.value)}
                className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
              >
                <option value="TODOS">Todos los estados</option>
                <option value="EN_REVISION">En revisión</option>
                <option value="APROBADO">Aprobados</option>
                <option value="OBSERVADO">Observados</option>
                <option value="RECHAZADO">Rechazados</option>
              </select>
            </div>

            <div>
              <label htmlFor="filtro-depto" className="mb-1 block text-xs font-medium text-muted">
                Departamento
              </label>
              <select
                id="filtro-depto"
                value={filtroDepartamento}
                onChange={(e) => setFiltroDepartamento(e.target.value)}
                className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
              >
                <option value="TODOS">Todos los departamentos</option>
                {departamentos.map((d) => (
                  <option key={d.id} value={d.id}>
                    Dpto. {d.numero}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label htmlFor="filtro-banco" className="mb-1 block text-xs font-medium text-muted">
                Banco
              </label>
              <input
                id="filtro-banco"
                type="text"
                list="lista-bancos"
                placeholder="Ej. BCP, BBVA..."
                value={filtroBanco}
                onChange={(e) => setFiltroBanco(e.target.value)}
                className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
              />
              <datalist id="lista-bancos">
                {bancosDisponibles.map((banco) => (
                  <option key={banco} value={banco} />
                ))}
              </datalist>
            </div>

            <div>
              <label htmlFor="filtro-desde" className="mb-1 block text-xs font-medium text-muted">
                Fecha desde
              </label>
              <input
                id="filtro-desde"
                type="date"
                value={filtroFechaDesde}
                onChange={(e) => setFiltroFechaDesde(e.target.value)}
                className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>

            <div>
              <label htmlFor="filtro-hasta" className="mb-1 block text-xs font-medium text-muted">
                Fecha hasta
              </label>
              <input
                id="filtro-hasta"
                type="date"
                value={filtroFechaHasta}
                onChange={(e) => setFiltroFechaHasta(e.target.value)}
                className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between text-xs text-muted">
            <span>
              Mostrando {comprobantesFiltrados.length} de {comprobantes.length} comprobantes
            </span>
          </div>
        </div>

        {comprobantesFiltrados.length === 0 ? (
          <div className="py-8 text-center">
            <p className="text-sm font-medium text-foreground">
              No se encontraron comprobantes con los filtros seleccionados.
            </p>
            <p className="mt-1 text-xs text-muted">
              Intenta ajustar las fechas o el estado seleccionado para ver más resultados.
            </p>
            {hayFiltrosActivos && (
              <div className="mt-4">
                <Button size="sm" variant="secondary" onClick={limpiarFiltros}>
                  Restablecer filtros
                </Button>
              </div>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <caption className="sr-only">
                Comprobantes de pago y estado de conciliación
              </caption>
              <thead>
                <tr className="border-b border-line text-left">
                  <th scope="col" className="p-3">Departamento</th>
                  <th scope="col" className="p-3">Banco / operación</th>
                  <th scope="col" className="p-3">Fecha</th>
                  <th scope="col" className="p-3 text-right">Monto</th>
                  <th scope="col" className="p-3">Estado</th>
                  <th scope="col" className="p-3 text-right">Acciones</th>
                </tr>
              </thead>
              <tbody>
                {comprobantesFiltrados.map((comprobante) => (
                  <tr key={comprobante.id} className="border-b border-line">
                    <th scope="row" className="p-3 text-left">
                      {departamentos.find((d) => d.id === comprobante.departamento_id)?.numero ?? comprobante.departamento_id}
                      <span className="mt-1 block text-xs font-normal text-muted">ID {comprobante.departamento_id}</span>
                    </th>
                    <td className="p-3">
                      {comprobante.banco} · {comprobante.numero_operacion}
                    </td>
                    <td className="p-3">{formatDate(comprobante.fecha_operacion)}</td>
                    <td className="p-3 text-right">
                      <MoneyAmount value={comprobante.monto} />
                    </td>
                    <td className="p-3">
                      <ComprobanteStatusChip status={comprobante.estado} />
                    </td>
                    <td className="p-3 text-right">
                      <VoucherDownloadButton comprobante={comprobante} />
                      {!isAuditor && comprobante.estado === "EN_REVISION" && (
                        <div className="flex justify-end gap-2">
                          <Button
                            size="sm"
                            onClick={() => onDecide(comprobante.id, "APROBADO")}
                          >
                            Aprobar
                          </Button>
                          <Button
                            size="sm"
                            variant="danger"
                            onClick={() => onDecide(comprobante.id, "RECHAZADO")}
                          >
                            Rechazar
                          </Button>
                          <Button
                            size="sm"
                            variant="secondary"
                            onClick={() => onDecide(comprobante.id, "OBSERVADO")}
                          >
                            Observar
                          </Button>
                        </div>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}
