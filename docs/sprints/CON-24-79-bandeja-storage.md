# CON-24 y CON-79 — Bandeja de conciliación y almacenamiento privado

Fecha de corte: 09/11/2026, America/Lima. Responsable: Brandon (Full Stack Developer).
Rama de trabajo: `feat/brandon-sprint-3`, creada desde `develop` en `aa2ee99`.
Historias cubiertas:
- [CON-24](https://tarquisoncco2.atlassian.net/browse/CON-24): Consultar la bandeja de conciliación (PAG-03).
- [CON-79](https://tarquisoncco2.atlassian.net/browse/CON-79): Consolidar almacenamiento privado de vouchers y documentos (Transversal).

---

## 1. Alcance y Funcionalidad Implementada

### A. CON-24: Bandeja de conciliación y filtros combinables
- **Endpoint:** `GET /api/v1/pagos/comprobantes`.
- **Filtros combinables:**
  - Rango de fechas bancarias: `fecha_desde` y `fecha_hasta` (rango inclusivo sobre `fecha_operacion`). Valida que `fecha_desde <= fecha_hasta` (422 `RANGO_FECHAS_INVALIDO`).
  - Departamento: `departamento_id` (UUID). Valida pertenencia para residentes.
  - Banco: `banco` (búsqueda insensible a mayúsculas/minúsculas o coincidencia de emisor).
  - Estado del comprobante: `estado` (`EN_REVISION`, `APROBADO`, `OBSERVADO`, `RECHAZADO`). Valida valores permitidos (422 `ESTADO_INVALIDO`).
- **Paginación y orden determinista:**
  - `limit` (default 50, máx 100) y `offset` (default 0).
  - Ordenación determinista y estable: `fecha_operacion DESC`, `creado_en DESC`, `id DESC`.
- **Seguridad RBAC y Aislamiento por Condominio:**
  - `SUPERADMIN` y `ADMIN_JUNTA`: acceso completo a la bandeja del condominio seleccionado.
  - `AUDITOR`: acceso completo en modo lectura dentro de su contexto.
  - `RESIDENTE`: acceso restringido estrictamente a sus unidades activas. Intentar consultar departamentos ajenos responde 403 `ACCESO_DENEGADO`.
- **Frontend y UX (`ConciliacionSection.tsx`):**
  - Barra de filtros interactiva con selectores para estado, departamento, banco (con datalist dinámico) y rango de fechas.
  - Contador reactivo: *"Mostrando X de Y comprobantes"*.
  - Botón de limpieza rápida de filtros y feedback de lista vacía filtrada.
  - Extensión de `fetchComprobantes` en `frontend/src/lib/api.ts` con tipado `FiltrosComprobantes`.

### B. CON-79: Almacenamiento privado consolidado
- **Módulo:** `src/modules/pagos/storage.py` (`VoucherStorage`).
- **Catálogo de clases de documentos:**
  - `TipoDocumento.VOUCHER`: límite de 5 MiB, formatos PNG, JPEG y PDF.
  - `TipoDocumento.PRORRATEO`: límite de 10 MiB, formatos PDF y DOCX.
- **Validación binaria (magic bytes):**
  - PDF: firma `%PDF-` y delimitador `%%EOF`, páginas válidas y sin encriptación.
  - PNG/JPEG: detección por cabecera binaria, raster validado con PIL y protección contra *DecompressionBomb*.
  - DOCX: contenedor ZIP con `[Content_Types].xml` y `word/document.xml`.
  - Rechazo con 415/422 ante scripts, HTML o ejecutables camuflados.
- **Mitigación contra Path Traversal:**
  - Nombres generados obligatoriamente con UUID v4 y extensión permitida.
  - Bloqueo y respuesta 404 controlada ante rutas con `..`, `/`, `\`, symlinks o esquemas remotos.
- **Protección de evidencias vigentes:**
  - Método `eliminar_seguro(nombre, es_vigente)`: rechaza la eliminación de evidencias activas con 409 `EVIDENCIA_VIGENTE_NO_ELIMINABLE`. Permite limpieza física de evidencias huérfanas tras rollbacks.

---

## 2. Contratos y Trazabilidad OpenAPI / SDD

- **OpenAPI 3.1:** Actualizado `specs/03-contracts/openapi/sprint-2.paths.yaml` con parámetros query para `/pagos/comprobantes` (`fecha_desde`, `fecha_hasta`, `departamento_id`, `banco`, `estado`, `limit`, `offset`) y trazabilidad de `x-historias: [CON-22, CON-23, CON-24]`.
- **Verificación SDD:** Cumplimiento total verificado con `scripts/verify_sdd_compliance.py` (cero floats, auditoría inmutable, esquemas alineados).

---

## 3. Pruebas y Resultados de Verificación

| Suite / Verificación | Pruebas | Resultado |
|---|---|---|
| `test_bandeja_conciliacion_con24.py` | 5 unitarias | ✅ 5 aprobadas (filtros, validaciones 422, ordenación, RBAC 403) |
| `test_storage_privado_con79.py` | 11 unitarias | ✅ 11 aprobadas (PDF, DOCX, límites 5/10 MiB, path traversal, eliminación segura 409) |
| Suite completa unitaria (`src/tests/unit/`) | 297 unitarias | ✅ 297 aprobadas (100% de éxito) |
| Verificador SDD (`scripts/verify_sdd_compliance.py`) | Reglas de arquitectura | ✅ Aprobado |
