import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { VoucherDownloadButton } from "@/components/domain/VoucherDownloadButton";
import { ComprobanteStatusChip } from "@/components/domain/ComprobanteStatusChip";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import { fetchComprobantes, type ComprobantePago, type DepartamentoRegistrado } from "@/lib/api";
import { formatDate } from "@/lib/format";

interface ConciliacionSectionProps {
  loading: boolean;
  comprobantes: ComprobantePago[];
  departamentos: DepartamentoRegistrado[];
  isAuditor: boolean;
  busy?: boolean;
  condominioId?: string | null;
  onResultado?: (id: string) => void;
  onDecide: (id: string, decision: "APROBADO" | "RECHAZADO" | "OBSERVADO") => void;
}

export function ConciliacionSection({
  loading: loadingProp,
  comprobantes: comprobantesProp,
  departamentos,
  isAuditor,
  busy = false,
  condominioId,
  onResultado,
  onDecide,
}: ConciliacionSectionProps) {
  const [filtroEstado, setFiltroEstado] = useState<string>("TODOS");
  const [filtroDepartamento, setFiltroDepartamento] = useState<string>("TODOS");
  const [filtroBanco, setFiltroBanco] = useState<string>("");
  const [filtroFechaDesde, setFiltroFechaDesde] = useState<string>("");
  const [filtroFechaHasta, setFiltroFechaHasta] = useState<string>("");
  const [limit, setLimit] = useState<number>(25);
  const [offset, setOffset] = useState<number>(0);

  const [itemsApi, setItemsApi] = useState<ComprobantePago[] | null>(null);
  const [loadingApi, setLoadingApi] = useState<boolean>(false);
  const [errorApi, setErrorApi] = useState<string | null>(null);
  const consultaActual = useRef(0);

  const hayFiltrosActivos =
    filtroEstado !== "TODOS" ||
    filtroDepartamento !== "TODOS" ||
    filtroBanco.trim() !== "" ||
    filtroFechaDesde !== "" ||
    filtroFechaHasta !== "" ||
    offset > 0;

  const consultarApi = useCallback(async () => {
    if (!condominioId) return;
    const consulta = ++consultaActual.current;
    setLoadingApi(true);
    setErrorApi(null);
    try {
      const data = await fetchComprobantes(condominioId, {
        departamentoId: filtroDepartamento,
        banco: filtroBanco,
        estado: filtroEstado,
        fechaDesde: filtroFechaDesde,
        fechaHasta: filtroFechaHasta,
        limit,
        offset,
      });
      if (consulta === consultaActual.current) setItemsApi(data);
    } catch (err) {
      if (consulta === consultaActual.current) setErrorApi(err instanceof Error ? err.message : "Error al consultar la bandeja de conciliación.");
    } finally {
      if (consulta === consultaActual.current) setLoadingApi(false);
    }
  }, [condominioId, filtroDepartamento, filtroBanco, filtroEstado, filtroFechaDesde, filtroFechaHasta, limit, offset]);

  useEffect(() => {
    const contador = consultaActual;
    if (!loadingProp && condominioId) {
      void consultarApi();
    } else {
      setItemsApi(null);
    }
    return () => { contador.current++; };
  }, [loadingProp, comprobantesProp, condominioId, consultarApi]);

  const limpiarFiltros = () => {
    setFiltroEstado("TODOS");
    setFiltroDepartamento("TODOS");
    setFiltroBanco("");
    setFiltroFechaDesde("");
    setFiltroFechaHasta("");
    setOffset(0);
    setItemsApi(null);
  };

  const bancosDisponibles = useMemo(() => {
    const setBancos = new Set<string>();
    for (const c of comprobantesProp) {
      if (c.banco) setBancos.add(c.banco);
    }
    return Array.from(setBancos).sort();
  }, [comprobantesProp]);

  const comprobantesMostrados = useMemo(() => {
    if (itemsApi !== null) return itemsApi;
    return comprobantesProp.filter((c) => {
      if (filtroEstado !== "TODOS" && c.estado !== filtroEstado) return false;
      if (filtroDepartamento !== "TODOS" && c.departamento_id !== filtroDepartamento) return false;
      if (filtroBanco.trim() && !c.banco.toLowerCase().includes(filtroBanco.trim().toLowerCase())) return false;
      if (filtroFechaDesde && c.fecha_operacion < filtroFechaDesde) return false;
      if (filtroFechaHasta && c.fecha_operacion > filtroFechaHasta) return false;
      return true;
    });
  }, [itemsApi, comprobantesProp, filtroEstado, filtroDepartamento, filtroBanco, filtroFechaDesde, filtroFechaHasta]);

  const paginaActual = Math.floor(offset / limit) + 1;

  if (loadingProp) return <SkeletonList rows={5} label="Cargando comprobantes" />;

  if (comprobantesProp.length === 0 && !hayFiltrosActivos) {
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
        <div className="mb-6 rounded-lg border border-line bg-surface-subtle p-4">
          <div className="mb-3 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">
              Filtros de búsqueda (CON-24)
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
                onChange={(e) => {
                  setFiltroEstado(e.target.value);
                  setOffset(0);
                }}
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
                onChange={(e) => {
                  setFiltroDepartamento(e.target.value);
                  setOffset(0);
                }}
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
                onChange={(e) => {
                  setFiltroBanco(e.target.value);
                  setOffset(0);
                }}
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
                onChange={(e) => {
                  setFiltroFechaDesde(e.target.value);
                  setOffset(0);
                }}
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
                onChange={(e) => {
                  setFiltroFechaHasta(e.target.value);
                  setOffset(0);
                }}
                className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
            <span>
              Mostrando {comprobantesMostrados.length} comprobante(s) en página {paginaActual}
            </span>
            <div className="flex items-center gap-2">
              <label htmlFor="limite-paginacion" className="font-medium">
                Por página:
              </label>
              <select
                id="limite-paginacion"
                value={limit}
                onChange={(e) => {
                  setLimit(Number(e.target.value));
                  setOffset(0);
                }}
                className="rounded border border-line bg-surface px-2 py-1 text-xs text-foreground"
              >
                <option value={10}>10</option>
                <option value={25}>25</option>
                <option value={50}>50</option>
              </select>
              <Button
                size="sm"
                variant="secondary"
                disabled={offset === 0 || loadingApi}
                onClick={() => setOffset(Math.max(0, offset - limit))}
              >
                Anterior
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={comprobantesMostrados.length < limit || loadingApi}
                onClick={() => setOffset(offset + limit)}
              >
                Siguiente
              </Button>
            </div>
          </div>
        </div>

        {errorApi && (
          <div className="mb-4 rounded border border-danger/40 bg-danger/10 p-3 text-xs text-danger">
            {errorApi}
          </div>
        )}

        {loadingApi ? (
          <SkeletonList rows={4} label="Actualizando comprobantes filtrados..." />
        ) : comprobantesMostrados.length === 0 ? (
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
                {comprobantesMostrados.map((comprobante) => (
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
                      <div className="flex items-center justify-end gap-2">
                        <VoucherDownloadButton comprobante={comprobante} />
                        {comprobante.estado !== "EN_REVISION" && onResultado && (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={busy}
                            onClick={() => onResultado(comprobante.id)}
                          >
                            Ver resultado
                          </Button>
                        )}
                        {!isAuditor && comprobante.estado === "EN_REVISION" && (
                          <div className="flex justify-end gap-2">
                            <Button
                              size="sm"
                              disabled={busy}
                              onClick={() => onDecide(comprobante.id, "APROBADO")}
                            >
                              Aprobar
                            </Button>
                            <Button
                              size="sm"
                              variant="danger"
                              disabled={busy}
                              onClick={() => onDecide(comprobante.id, "RECHAZADO")}
                            >
                              Rechazar
                            </Button>
                            <Button
                              size="sm"
                              variant="secondary"
                              disabled={busy}
                              onClick={() => onDecide(comprobante.id, "OBSERVADO")}
                            >
                              Observar
                            </Button>
                          </div>
                        )}
                      </div>
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
