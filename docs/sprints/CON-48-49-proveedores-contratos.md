# Entrega Sprint 4 — CON-48 y CON-49: Proveedores y Contratos

**Responsable:** Brandon (Full Stack Developer)  
**Fecha:** 25/11/2026  
**Rama:** `feat/CON-48-49-proveedores-contratos`  
**Tickets:**
- **CON-48:** Directorio de proveedores con RUC único por condominio y enlaces a contratos, egresos e incidencias.
- **CON-49:** Custodia digital de contratos y pólizas con vigencia, alertas preventivas (60/30 días) y versionamiento privado de documentos.

---

## 1. Alcance de Implementación

### CON-48: Directorio de Proveedores
1. **Modelo de Datos (`proveedores`):**
   - Identificación formal mediante RUC de 11 dígitos, normalizado y con restricción de unicidad por condominio (`uq_proveedor_condominio_ruc`).
   - Razón social, nombre comercial opcional, rubro/especialidad normalizado (`MANTENIMIENTO_PREVENTIVO`, `SEGURIDAD`, `LIMPIEZA`, etc.).
   - Contacto técnico/comercial (nombre, teléfono, correo electrónico validado).
   - Dirección física y notas adicionales.
   - Estado de habilitación (`activo: bool`) y control de versiones (`version: int`).
   - Trazabilidad y auditoría inmutable (`creado_por`, `creado_en`, `actualizado_en`).
2. **Endpoints API REST (`/condominios/{cid}/proveedores`):**
   - `POST /condominios/{cid}/proveedores`: Registro de proveedor con validación de RUC y prevención de duplicados (`409 PROVEEDOR_RUC_DUPLICADO`).
   - `GET /condominios/{cid}/proveedores`: Listado filtrable por rubro, estado activo y búsqueda predictiva de texto/RUC.
   - `GET /condominios/{cid}/proveedores/{id}`: Detalle completo con conteo de contratos vigentes, egresos e incidencias vinculadas.
   - `PATCH /condominios/{cid}/proveedores/{id}`: Actualización de datos de contacto o estado activo con incremento de versión.

### CON-49: Repositorio de Contratos y Pólizas
1. **Modelo de Datos (`contratos_proveedor` y `documentos_contrato_version`):**
   - Número de contrato, descripción y tipo de documento (`CONTRATO_SERVICIO`, `POLIZA_SEGURO`, `ADDENDA`, `ACTA_CONFORMIDAD`).
   - Monto mensual en `Numeric(12, 2)` cumpliendo la regla Zero-Float (ADR-002) y moneda (`PEN`/`USD`).
   - Fechas de vigencia (`fecha_inicio` y `fecha_fin`) con validación de rango.
   - Contacto y teléfono de emergencias 24/7.
   - Estados de contrato: `VIGENTE`, `POR_VENCER`, `VENCIDO`, `RENOVADO`, `CANCELADO`.
   - Cálculo dinámico de días restantes con alertas tempranas:
     - **≤ 60 días:** Alerta preventiva para licitación o renovación.
     - **≤ 30 días:** Alerta crítica en el dashboard de la Junta.
2. **Almacenamiento Privado y Versionamiento Inmutable:**
   - Tabla `documentos_contrato_version` con almacenamiento seguro en BD (`LargeBinary, deferred=True`), reutilizando el patrón de almacenamiento privado de CON-79.
   - Límite de archivo fijado en 3 MiB (adecuado para entorno Vercel Hobby / Demo).
   - Validación binaria estricta de Magic Bytes (firma `%PDF`).
   - Mitigación de Path Traversal en el nombre del archivo.
   - Cálculo de Hash SHA-256.
   - Reemplazo inmutable: cada nueva subida o addenda genera una nueva versión (`v1`, `v2`, `v3`...), conservando el historial previo para auditoría.
3. **Endpoints API REST:**
   - `POST /condominios/{cid}/proveedores/{id}/contratos`: Crear contrato asociado a proveedor.
   - `GET /condominios/{cid}/contratos`: Listar todos los contratos del condominio con estados y días restantes.
   - `GET /condominios/{cid}/contratos/{id}`: Detalle de contrato e historial de todas sus versiones.
   - `PATCH /condominios/{cid}/contratos/{id}`: Modificación de términos, montos o fecha de fin.
   - `POST /condominios/{cid}/contratos/{id}/versiones`: Subida multipart de documento PDF con motivo de reemplazo opcional.
   - `GET /condominios/{cid}/contratos/{id}/versiones/{v}/descargar`: Descarga autorizada y privada del archivo PDF.

---

## 2. Frontend — Portal de Junta Directiva
- **Componente Principal:** `frontend/src/features/junta/ProveedoresSection.tsx`
- **Navegación:** Integrado en la barra lateral del portal de Junta (`frontend/src/features/junta/JuntaNav.tsx` y `JuntaPortal.tsx`).
- **Pestaña Directorio:**
  - Búsqueda en vivo por texto, filtro por rubro y por estado activo/inactivo.
  - Formulario modal con validación estricta de RUC peruano de 11 dígitos.
  - Cambio rápido de estado Activar/Desactivar.
- **Pestaña Contratos:**
  - Tabla con identificación de contratos, montos y vigencias.
  - Badges visuales de alertas:
    - Verde: `VIGENTE` (> 60 días).
    - Amarillo: `60 DÍAS (PREVENTIVO)`.
    - Rojo/Naranja: `30 DÍAS (CRÍTICO)` o `VENCIDO`.
  - Botón de descarga/visualización directa de la versión actual.
  - Modal para subir addenda o nueva versión con motivo de reemplazo.
  - Modal de historial con listado de todas las versiones anteriores, tamaños y fechas de subida.

---

## 3. Seguridad y Control de Acceso (RBAC)
- **ADMIN_JUNTA y SUPERADMIN:** Permiso completo de lectura y escritura (`autorizar_condominio(actor, cid, escritura=True)`).
- **AUDITOR:** Acceso de solo lectura a proveedores, contratos y descarga de PDFs dentro de su condominio; cualquier intento de mutación devuelve `403 ACCESO_DENEGADO`.
- **Aislamiento Multi-Tenant:** Ningún usuario puede consultar ni registrar proveedores o contratos fuera de su contexto autorizado de condominio.

---

## 4. Evidencia de Pruebas

1. **Pruebas Unitarias (`src/tests/unit/test_proveedores_contratos_con48_con49.py`):**
   - `test_crear_proveedor_exitoso` (PASSED)
   - `test_ruc_duplicado_mismo_condominio_rechazado` (PASSED)
   - `test_listar_y_filtrar_proveedores` (PASSED)
   - `test_contrato_registro_y_calculo_vigencia` (PASSED)
   - `test_subida_version_documento_pdf_segura` (PASSED)
   - `test_rechazo_archivo_no_pdf` (PASSED)
   - **Resultado:** 6 de 6 pruebas unitarias aprobadas.

2. **Pruebas de Aceptación BDD (`src/tests/bdd/test_proveedores_contratos_bdd.py`):**
   - `test_registro_exitoso_de_proveedor_con_ruc_único_por_condominio` (PASSED)
   - `test_rechazo_de_ruc_duplicado_dentro_del_mismo_condominio` (PASSED)
   - `test_registro_de_contrato_y_cálculo_de_alertas_de_vencimiento` (PASSED)
   - `test_custodia_digital_y_versionamiento_inmutable_de_contratos_pdf` (PASSED)
   - `test_restricción_de_permisos_y_aislamiento_por_rol` (PASSED)
   - **Resultado:** 5 de 5 escenarios BDD aprobados.

3. **Verificación SDD (`scripts/verify_sdd_compliance.py`):**
   - 100% de cumplimiento: estructura de dominios, contratos OpenAPI, diccionario de datos, regla Zero-Float (ADR-002) y campos de auditoría inmutables.
