"use client";

import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { EmptyState, SkeletonList } from "@/components/ui/Feedback";
import {
  actualizarContrato,
  actualizarProveedor,
  crearContrato,
  crearProveedor,
  listarContratos,
  listarProveedores,
  obtenerContrato,
  subirDocumentoContrato,
  urlDescargaDocumentoContrato,
  type Contrato,
  type ContratoDetalle,
  type CrearContratoPayload,
  type CrearProveedorPayload,
  type DocumentoVersion,
  type Proveedor,
} from "@/lib/api";

interface Props {
  condominioId: string | null;
  esSuperAdmin?: boolean;
}

const RUBROS_SUGERIDOS = [
  "MANTENIMIENTO_PREVENTIVO",
  "SEGURIDAD",
  "LIMPIEZA",
  "SERVICIOS_BASICOS",
  "ASCENSORES",
  "BOMBAS_AGUA",
  "EXTINTORES",
  "ADMINISTRATIVO",
  "OTRO",
];

export function ProveedoresSection({ condominioId }: Props) {
  const [tabActiva, setTabActiva] = useState<"PROVEEDORES" | "CONTRATOS">("PROVEEDORES");
  const [proveedores, setProveedores] = useState<Proveedor[]>([]);
  const [contratos, setContratos] = useState<Contrato[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [exito, setExito] = useState<string | null>(null);

  // Filtros
  const [filtroBuscar, setFiltroBuscar] = useState("");
  const [filtroRubro, setFiltroRubro] = useState("TODOS");
  const [filtroEstadoProv, setFiltroEstadoProv] = useState<string>("TODOS");

  // Modales
  const [modalNuevoProveedor, setModalNuevoProveedor] = useState(false);
  const [modalNuevoContrato, setModalNuevoContrato] = useState(false);
  const [modalVersionado, setModalVersionado] = useState<Contrato | null>(null);
  const [modalHistorial, setModalHistorial] = useState<ContratoDetalle | null>(null);

  // Formulario Nuevo Proveedor
  const [formProv, setFormProv] = useState<CrearProveedorPayload>({
    ruc: "",
    razon_social: "",
    nombre_comercial: "",
    rubro: "MANTENIMIENTO_PREVENTIVO",
    contacto_nombre: "",
    contacto_telefono: "",
    contacto_email: "",
    direccion: "",
    notas: "",
  });

  // Formulario Nuevo Contrato
  const [formCtr, setFormCtr] = useState<CrearContratoPayload & { proveedor_id: string }>({
    proveedor_id: "",
    numero_contrato: "",
    tipo_documento: "CONTRATO_SERVICIO",
    descripcion: "",
    monto_mensual: "",
    moneda: "PEN",
    fecha_inicio: "",
    fecha_fin: "",
    contacto_emergencia: "",
    contacto_emergencia_telefono: "",
  });

  // Formulario Subir/Reemplazar Versión
  const [archivoSeleccionado, setArchivoSeleccionado] = useState<File | null>(null);
  const [motivoReemplazo, setMotivoReemplazo] = useState("");

  const cargarDatos = useCallback(async () => {
    if (!condominioId) return;
    setLoading(true);
    setError(null);
    try {
      const [listaProv, listaCtr] = await Promise.all([
        listarProveedores(condominioId, {
          rubro: filtroRubro !== "TODOS" ? filtroRubro : undefined,
          buscar: filtroBuscar.trim() || undefined,
          activo:
            filtroEstadoProv === "ACTIVO"
              ? true
              : filtroEstadoProv === "INACTIVO"
              ? false
              : undefined,
        }),
        listarContratos(condominioId),
      ]);
      setProveedores(listaProv);
      setContratos(listaCtr);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al cargar los datos.");
    } finally {
      setLoading(false);
    }
  }, [condominioId, filtroRubro, filtroBuscar, filtroEstadoProv]);

  useEffect(() => {
    void cargarDatos();
  }, [cargarDatos]);

  const handleCrearProveedor = async (e: FormEvent) => {
    e.preventDefault();
    if (!condominioId) return;
    if (formProv.ruc.length !== 11 || !/^\d+$/.test(formProv.ruc)) {
      setError("El RUC debe tener exactamente 11 dígitos numéricos.");
      return;
    }
    setBusy("crear_proveedor");
    setError(null);
    try {
      await crearProveedor(condominioId, formProv);
      setExito("Proveedor registrado exitosamente.");
      setModalNuevoProveedor(false);
      setFormProv({
        ruc: "",
        razon_social: "",
        nombre_comercial: "",
        rubro: "MANTENIMIENTO_PREVENTIVO",
        contacto_nombre: "",
        contacto_telefono: "",
        contacto_email: "",
        direccion: "",
        notas: "",
      });
      await cargarDatos();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al registrar el proveedor.");
    } finally {
      setBusy(null);
    }
  };

  const handleCrearContrato = async (e: FormEvent) => {
    e.preventDefault();
    if (!condominioId || !formCtr.proveedor_id) {
      setError("Seleccione un proveedor para el contrato.");
      return;
    }
    setBusy("crear_contrato");
    setError(null);
    try {
      await crearContrato(condominioId, formCtr.proveedor_id, {
        numero_contrato: formCtr.numero_contrato,
        tipo_documento: formCtr.tipo_documento,
        descripcion: formCtr.descripcion,
        monto_mensual: formCtr.monto_mensual || null,
        moneda: formCtr.moneda,
        fecha_inicio: formCtr.fecha_inicio,
        fecha_fin: formCtr.fecha_fin,
        contacto_emergencia: formCtr.contacto_emergencia || null,
        contacto_emergencia_telefono: formCtr.contacto_emergencia_telefono || null,
      });
      setExito("Contrato registrado con éxito.");
      setModalNuevoContrato(false);
      await cargarDatos();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al crear el contrato.");
    } finally {
      setBusy(null);
    }
  };

  const handleSubirVersion = async (e: FormEvent) => {
    e.preventDefault();
    if (!condominioId || !modalVersionado || !archivoSeleccionado) {
      setError("Seleccione un archivo PDF válido.");
      return;
    }
    setBusy("subir_archivo");
    setError(null);
    try {
      await subirDocumentoContrato(
        condominioId,
        modalVersionado.id,
        archivoSeleccionado,
        motivoReemplazo.trim() || undefined
      );
      setExito("Documento versionado y almacenado de forma privada.");
      setModalVersionado(null);
      setArchivoSeleccionado(null);
      setMotivoReemplazo("");
      await cargarDatos();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al subir la versión del documento.");
    } finally {
      setBusy(null);
    }
  };

  const handleVerHistorial = async (contratoId: string) => {
    if (!condominioId) return;
    setBusy(`historial_${contratoId}`);
    try {
      const detalle = await obtenerContrato(condominioId, contratoId);
      setModalHistorial(detalle);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al obtener el historial.");
    } finally {
      setBusy(null);
    }
  };

  const handleToggleActivo = async (p: Proveedor) => {
    if (!condominioId) return;
    setBusy(`toggle_${p.id}`);
    try {
      await actualizarProveedor(condominioId, p.id, { activo: !p.activo });
      await cargarDatos();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Error al actualizar estado.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      {/* Encabezado y Navegación de Tabs */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-xl font-bold tracking-tight text-foreground">
            Proveedores y Contratos
          </h2>
          <p className="text-sm text-muted">
            Directorio oficial de contratistas, custodia digital de pólizas y alertas de vencimiento.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {tabActiva === "PROVEEDORES" ? (
            <Button
              variant="primary"
              onClick={() => setModalNuevoProveedor(true)}
              disabled={loading}
            >
              + Nuevo Proveedor
            </Button>
          ) : (
            <Button
              variant="primary"
              onClick={() => setModalNuevoContrato(true)}
              disabled={loading || proveedores.length === 0}
            >
              + Nuevo Contrato / Póliza
            </Button>
          )}
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-line">
        <button
          type="button"
          onClick={() => setTabActiva("PROVEEDORES")}
          className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
            tabActiva === "PROVEEDORES"
              ? "border-accent text-accent"
              : "border-transparent text-muted hover:text-foreground"
          }`}
        >
          Directorio de Proveedores ({proveedores.length})
        </button>
        <button
          type="button"
          onClick={() => setTabActiva("CONTRATOS")}
          className={`border-b-2 px-4 py-2 text-sm font-medium transition-colors ${
            tabActiva === "CONTRATOS"
              ? "border-accent text-accent"
              : "border-transparent text-muted hover:text-foreground"
          }`}
        >
          Contratos y Pólizas ({contratos.length})
        </button>
      </div>

      {error && <Alert tone="danger" title="Error" onDismiss={() => setError(null)}>{error}</Alert>}
      {exito && <Alert tone="success" title="Completado" onDismiss={() => setExito(null)}>{exito}</Alert>}

      {/* ==================================================================== */}
      {/* TAB 1: DIRECTORIO DE PROVEEDORES (CON-48) */}
      {/* ==================================================================== */}
      {tabActiva === "PROVEEDORES" && (
        <Card>
          <CardHeader
            title="Directorio de Contratistas y Proveedores"
            description="Proveedores homologados con RUC único para imputar egresos, vincular incidencias y custodiar contratos."
          />
          <CardBody>
            {/* Barra de Filtros */}
            <div className="mb-6 grid grid-cols-1 gap-3 rounded-lg border border-line bg-surface-subtle p-4 sm:grid-cols-3">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted">Buscar proveedor o RUC</label>
                <input
                  type="text"
                  placeholder="Ej. Otis, 20551122334..."
                  value={filtroBuscar}
                  onChange={(e) => setFiltroBuscar(e.target.value)}
                  className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
                />
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted">Especialidad / Rubro</label>
                <select
                  value={filtroRubro}
                  onChange={(e) => setFiltroRubro(e.target.value)}
                  className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
                >
                  <option value="TODOS">Todos los rubros</option>
                  {RUBROS_SUGERIDOS.map((r) => (
                    <option key={r} value={r}>
                      {r.replace(/_/g, " ")}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted">Estado</label>
                <select
                  value={filtroEstadoProv}
                  onChange={(e) => setFiltroEstadoProv(e.target.value)}
                  className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:outline-none focus:ring-1 focus:ring-accent"
                >
                  <option value="TODOS">Todos los estados</option>
                  <option value="ACTIVO">Solo Activos</option>
                  <option value="INACTIVO">Inactivos</option>
                </select>
              </div>
            </div>

            {loading ? (
              <SkeletonList rows={4} label="Cargando proveedores..." />
            ) : proveedores.length === 0 ? (
              <EmptyState
                title="No se encontraron proveedores"
                description="No hay proveedores que coincidan con los filtros o aún no se han registrado contratistas."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-line bg-surface-subtle text-xs font-medium uppercase text-muted">
                    <tr>
                      <th className="p-3">RUC</th>
                      <th className="p-3">Razón Social / Nombre Comercial</th>
                      <th className="p-3">Rubro</th>
                      <th className="p-3">Contacto Principal</th>
                      <th className="p-3">Estado</th>
                      <th className="p-3 text-right">Acciones</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {proveedores.map((p) => (
                      <tr key={p.id} className="hover:bg-surface-subtle/50">
                        <td className="p-3 font-mono font-medium">{p.ruc}</td>
                        <td className="p-3">
                          <div className="font-semibold text-foreground">{p.razon_social}</div>
                          {p.nombre_comercial && (
                            <div className="text-xs text-muted">({p.nombre_comercial})</div>
                          )}
                        </td>
                        <td className="p-3">
                          <Badge tone="neutral">{p.rubro.replace(/_/g, " ")}</Badge>
                        </td>
                        <td className="p-3">
                          <div>{p.contacto_nombre}</div>
                          <div className="text-xs text-muted">{p.contacto_telefono} · {p.contacto_email}</div>
                        </td>
                        <td className="p-3">
                          <Badge tone={p.activo ? "success" : "neutral"}>
                            {p.activo ? "ACTIVO" : "INACTIVO"}
                          </Badge>
                        </td>
                        <td className="p-3 text-right">
                          <button
                            type="button"
                            onClick={() => handleToggleActivo(p)}
                            disabled={busy === `toggle_${p.id}`}
                            className="text-xs font-medium text-accent hover:underline"
                          >
                            {p.activo ? "Desactivar" : "Activar"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* ==================================================================== */}
      {/* TAB 2: CONTRATOS Y PÓLIZAS CON VIGENCIA Y VERSIONES (CON-49) */}
      {/* ==================================================================== */}
      {tabActiva === "CONTRATOS" && (
        <Card>
          <CardHeader
            title="Custodia de Contratos y Pólizas"
            description="Alertas preventivas de vencimiento a los 60 y 30 días, almacenamiento privado e historial inmutable de addendas."
          />
          <CardBody>
            {loading ? (
              <SkeletonList rows={4} label="Cargando contratos..." />
            ) : contratos.length === 0 ? (
              <EmptyState
                title="No hay contratos registrados"
                description="Registra contratos de mantenimiento o pólizas de seguro vinculados a un proveedor."
              />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-line bg-surface-subtle text-xs font-medium uppercase text-muted">
                    <tr>
                      <th className="p-3">Contrato #</th>
                      <th className="p-3">Tipo</th>
                      <th className="p-3">Descripción</th>
                      <th className="p-3">Monto Mensual</th>
                      <th className="p-3">Vigencia</th>
                      <th className="p-3">Estado / Alerta</th>
                      <th className="p-3 text-right">Documento / Versión</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {contratos.map((c) => {
                      const esCritico = c.dias_restantes <= 30 && c.dias_restantes >= 0;
                      const esPreventivo = c.dias_restantes > 30 && c.dias_restantes <= 60;
                      const esVencido = c.dias_restantes < 0;

                      return (
                        <tr key={c.id} className="hover:bg-surface-subtle/50">
                          <td className="p-3 font-mono font-semibold text-foreground">
                            {c.numero_contrato}
                          </td>
                          <td className="p-3">
                            <Badge tone="neutral">{c.tipo_documento.replace(/_/g, " ")}</Badge>
                          </td>
                          <td className="p-3">
                            <div className="max-w-xs truncate">{c.descripcion}</div>
                            {c.contacto_emergencia && (
                              <div className="text-xs text-muted">
                                Emergencia: {c.contacto_emergencia} ({c.contacto_emergencia_telefono})
                              </div>
                            )}
                          </td>
                          <td className="p-3 font-mono font-medium">
                            {c.monto_mensual ? `${c.moneda} ${c.monto_mensual}` : "No aplica"}
                          </td>
                          <td className="p-3 text-xs">
                            <div>Desde: {c.fecha_inicio}</div>
                            <div>Hasta: {c.fecha_fin}</div>
                          </td>
                          <td className="p-3">
                            {esVencido ? (
                              <Badge tone="danger">VENCIDO</Badge>
                            ) : esCritico ? (
                              <Badge tone="danger">{c.dias_restantes} DÍAS (CRÍTICO 30D)</Badge>
                            ) : esPreventivo ? (
                              <Badge tone="warning">{c.dias_restantes} DÍAS (PREVENTIVO 60D)</Badge>
                            ) : (
                              <Badge tone="success">VIGENTE ({c.dias_restantes}d)</Badge>
                            )}
                          </td>
                          <td className="p-3 text-right">
                            <div className="flex items-center justify-end gap-2">
                              {c.tiene_documento && condominioId && (
                                <a
                                  href={urlDescargaDocumentoContrato(condominioId, c.id, c.version_actual)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="rounded border border-line bg-surface px-2 py-1 text-xs font-medium text-foreground hover:bg-surface-subtle"
                                >
                                  Ver PDF (v{c.version_actual})
                                </a>
                              )}
                              <button
                                type="button"
                                onClick={() => setModalVersionado(c)}
                                className="rounded bg-accent/10 px-2 py-1 text-xs font-medium text-accent hover:bg-accent/20"
                              >
                                {c.tiene_documento ? "Reemplazar" : "Subir PDF"}
                              </button>
                              <button
                                type="button"
                                onClick={() => handleVerHistorial(c.id)}
                                className="text-xs text-muted hover:underline"
                              >
                                Historial
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </CardBody>
        </Card>
      )}

      {/* MODAL: NUEVO PROVEEDOR */}
      {modalNuevoProveedor && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-xl border border-line bg-surface p-6 shadow-xl">
            <h3 className="mb-1 text-lg font-bold text-foreground">Registrar Nuevo Proveedor</h3>
            <p className="mb-4 text-xs text-muted">
              El RUC debe ser único dentro de este condominio.
            </p>
            <form onSubmit={handleCrearProveedor} className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">RUC (11 dígitos) *</label>
                  <input
                    type="text"
                    required
                    maxLength={11}
                    value={formProv.ruc}
                    onChange={(e) => setFormProv({ ...formProv, ruc: e.target.value.replace(/\D/g, "") })}
                    placeholder="20XXXXXXXXX"
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Rubro / Especialidad *</label>
                  <select
                    value={formProv.rubro}
                    onChange={(e) => setFormProv({ ...formProv, rubro: e.target.value })}
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  >
                    {RUBROS_SUGERIDOS.map((r) => (
                      <option key={r} value={r}>
                        {r.replace(/_/g, " ")}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted">Razón Social *</label>
                <input
                  type="text"
                  required
                  value={formProv.razon_social}
                  onChange={(e) => setFormProv({ ...formProv, razon_social: e.target.value })}
                  placeholder="Empresa Contratista SAC"
                  className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Nombre Comercial</label>
                  <input
                    type="text"
                    value={formProv.nombre_comercial || ""}
                    onChange={(e) => setFormProv({ ...formProv, nombre_comercial: e.target.value })}
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Contacto (Nombre) *</label>
                  <input
                    type="text"
                    required
                    value={formProv.contacto_nombre}
                    onChange={(e) => setFormProv({ ...formProv, contacto_nombre: e.target.value })}
                    placeholder="Ing. de Cuenta"
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Teléfono Contacto *</label>
                  <input
                    type="tel"
                    required
                    value={formProv.contacto_telefono}
                    onChange={(e) => setFormProv({ ...formProv, contacto_telefono: e.target.value })}
                    placeholder="999888777"
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Correo Electrónico *</label>
                  <input
                    type="email"
                    required
                    value={formProv.contacto_email}
                    onChange={(e) => setFormProv({ ...formProv, contacto_email: e.target.value })}
                    placeholder="contacto@empresa.pe"
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" onClick={() => setModalNuevoProveedor(false)} type="button">
                  Cancelar
                </Button>
                <Button variant="primary" type="submit" disabled={busy === "crear_proveedor"}>
                  {busy === "crear_proveedor" ? "Guardando..." : "Guardar Proveedor"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: NUEVO CONTRATO */}
      {modalNuevoContrato && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-lg rounded-xl border border-line bg-surface p-6 shadow-xl">
            <h3 className="mb-1 text-lg font-bold text-foreground">Nuevo Contrato o Póliza</h3>
            <p className="mb-4 text-xs text-muted">Vincular a un proveedor del directorio.</p>
            <form onSubmit={handleCrearContrato} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted">Proveedor *</label>
                <select
                  required
                  value={formCtr.proveedor_id}
                  onChange={(e) => setFormCtr({ ...formCtr, proveedor_id: e.target.value })}
                  className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                >
                  <option value="">Seleccione un proveedor...</option>
                  {proveedores.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.razon_social} ({p.ruc})
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Número de Contrato *</label>
                  <input
                    type="text"
                    required
                    value={formCtr.numero_contrato}
                    onChange={(e) => setFormCtr({ ...formCtr, numero_contrato: e.target.value })}
                    placeholder="CTR-2026-001"
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Tipo Documento *</label>
                  <select
                    value={formCtr.tipo_documento}
                    onChange={(e) =>
                      setFormCtr({
                        ...formCtr,
                        tipo_documento: e.target.value as "CONTRATO_SERVICIO" | "POLIZA_SEGURO" | "ADDENDA",
                      })
                    }
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  >
                    <option value="CONTRATO_SERVICIO">Contrato de Servicio</option>
                    <option value="POLIZA_SEGURO">Póliza de Seguro</option>
                    <option value="ADDENDA">Addenda</option>
                    <option value="ACTA_CONFORMIDAD">Acta de Conformidad</option>
                  </select>
                </div>
              </div>
              <div>
                <label className="mb-1 block text-xs font-medium text-muted">Descripción *</label>
                <textarea
                  required
                  rows={2}
                  value={formCtr.descripcion}
                  onChange={(e) => setFormCtr({ ...formCtr, descripcion: e.target.value })}
                  placeholder="Alcance del servicio o cobertura de la póliza..."
                  className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Monto Mensual</label>
                  <input
                    type="number"
                    step="0.01"
                    value={formCtr.monto_mensual || ""}
                    onChange={(e) => setFormCtr({ ...formCtr, monto_mensual: e.target.value })}
                    placeholder="0.00"
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Moneda</label>
                  <select
                    value={formCtr.moneda}
                    onChange={(e) => setFormCtr({ ...formCtr, moneda: e.target.value as "PEN" | "USD" })}
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  >
                    <option value="PEN">Soles (PEN)</option>
                    <option value="USD">Dólares (USD)</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Fecha Inicio *</label>
                  <input
                    type="date"
                    required
                    value={formCtr.fecha_inicio}
                    onChange={(e) => setFormCtr({ ...formCtr, fecha_inicio: e.target.value })}
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  />
                </div>
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Fecha Fin *</label>
                  <input
                    type="date"
                    required
                    value={formCtr.fecha_fin}
                    onChange={(e) => setFormCtr({ ...formCtr, fecha_fin: e.target.value })}
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  />
                </div>
              </div>
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" onClick={() => setModalNuevoContrato(false)} type="button">
                  Cancelar
                </Button>
                <Button variant="primary" type="submit" disabled={busy === "crear_contrato"}>
                  {busy === "crear_contrato" ? "Guardando..." : "Crear Contrato"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: SUBIR O REEMPLAZAR DOCUMENTO (CON-49) */}
      {modalVersionado && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-md rounded-xl border border-line bg-surface p-6 shadow-xl">
            <h3 className="mb-1 text-lg font-bold text-foreground">
              {modalVersionado.tiene_documento ? "Reemplazar Versión de Documento" : "Subir Documento PDF"}
            </h3>
            <p className="mb-4 text-xs text-muted">
              Contrato: <span className="font-semibold text-foreground">{modalVersionado.numero_contrato}</span>
              {modalVersionado.tiene_documento && (
                <span className="ml-1 text-accent">· Versión actual: v{modalVersionado.version_actual}</span>
              )}
            </p>
            <form onSubmit={handleSubirVersion} className="space-y-4">
              <div>
                <label className="mb-1 block text-xs font-medium text-muted">Seleccionar archivo PDF (máx. 3 MiB) *</label>
                <input
                  type="file"
                  accept="application/pdf"
                  required
                  onChange={(e) => setArchivoSeleccionado(e.target.files?.[0] || null)}
                  className="w-full text-xs text-muted file:mr-2 file:rounded file:border-0 file:bg-surface-subtle file:px-3 file:py-2 file:text-xs file:font-semibold file:text-foreground hover:file:bg-line"
                />
              </div>
              {modalVersionado.tiene_documento && (
                <div>
                  <label className="mb-1 block text-xs font-medium text-muted">Motivo del reemplazo / Addenda *</label>
                  <textarea
                    rows={2}
                    required
                    value={motivoReemplazo}
                    onChange={(e) => setMotivoReemplazo(e.target.value)}
                    placeholder="Ej. Renovación de póliza 2026, adición de cláusula..."
                    className="w-full rounded border border-line bg-surface p-2 text-sm text-foreground focus:ring-1 focus:ring-accent"
                  />
                </div>
              )}
              <div className="flex justify-end gap-2 pt-2">
                <Button variant="secondary" onClick={() => setModalVersionado(null)} type="button">
                  Cancelar
                </Button>
                <Button variant="primary" type="submit" disabled={busy === "subir_archivo" || !archivoSeleccionado}>
                  {busy === "subir_archivo" ? "Procesando..." : "Subir Versión"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* MODAL: HISTORIAL DE VERSIONES AUDITADO (CON-49) */}
      {modalHistorial && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="w-full max-w-2xl rounded-xl border border-line bg-surface p-6 shadow-xl">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-bold text-foreground">
                  Historial de Versiones del Documento
                </h3>
                <p className="text-xs text-muted">
                  Contrato {modalHistorial.numero_contrato} · Proveedor: {modalHistorial.proveedor_razon_social}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setModalHistorial(null)}
                className="text-sm font-bold text-muted hover:text-foreground"
              >
                ✕
              </button>
            </div>
            {modalHistorial.versiones.length === 0 ? (
              <EmptyState
                title="Sin documentos cargados"
                description="Este contrato aún no tiene archivos PDF subidos."
              />
            ) : (
              <div className="max-h-80 overflow-y-auto">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-line bg-surface-subtle text-xs font-medium uppercase text-muted">
                    <tr>
                      <th className="p-2">Versión</th>
                      <th className="p-2">Archivo</th>
                      <th className="p-2">Tamaño</th>
                      <th className="p-2">Motivo</th>
                      <th className="p-2">Fecha</th>
                      <th className="p-2 text-right">Descargar</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {modalHistorial.versiones.map((v) => (
                      <tr key={v.id} className="hover:bg-surface-subtle/50">
                        <td className="p-2 font-mono font-semibold">v{v.version}</td>
                        <td className="p-2 max-w-[150px] truncate text-xs">{v.archivo_nombre}</td>
                        <td className="p-2 text-xs font-mono">
                          {(v.archivo_tamano_bytes / 1024).toFixed(1)} KB
                        </td>
                        <td className="p-2 text-xs text-muted">
                          {v.motivo_reemplazo || "Versión inicial"}
                        </td>
                        <td className="p-2 text-xs text-muted">
                          {new Date(v.subido_en).toLocaleDateString()}
                        </td>
                        <td className="p-2 text-right">
                          {condominioId && (
                            <a
                              href={urlDescargaDocumentoContrato(condominioId, modalHistorial.id, v.version)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="rounded border border-line bg-surface px-2 py-1 text-xs font-medium text-accent hover:bg-surface-subtle"
                            >
                              Descargar
                            </a>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="mt-4 flex justify-end">
              <Button variant="secondary" onClick={() => setModalHistorial(null)}>
                Cerrar
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
