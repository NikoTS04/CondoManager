# Plan de unificación de nombres e identificadores visibles

**Proyecto:** CondoManager  
**Estado:** Pendiente de implementación

## Objetivo

Permitir que los usuarios reconozcan y seleccionen personas y condominios por su nombre, sin tener que copiar ni interpretar UUID.

Ejemplos del resultado esperado:

- `Condominio · 3fa85f64-…` → **Condominio · Villa Bonita**.
- `Aprobado por: 8e12a9…` → **Aprobado por: María Elena Torres**.
- Campo «UUID del usuario entrante» → **Buscador para seleccionar una persona por nombre y apellido**.

Los UUID seguirán siendo los identificadores internos de las operaciones. La interfaz y las salidas destinadas a personas mostrarán información legible.

## 1. Unificar cómo se presentan los nombres

Establecer las siguientes reglas para toda la aplicación:

| Entidad | Información que se mostrará |
| --- | --- |
| Usuario | Nombre y apellido completos. |
| Condominio | Nombre registrado del condominio. |
| Departamento | Edificio y número de departamento. |
| Presupuesto | Periodo, versión y estado. |
| Comprobante | Banco y número de operación. |
| Evidencia de pago | Fecha y etiqueta de revisión. |
| Concepto presupuestal | Código y descripción. |

### Reglas transversales

- Componer el nombre completo con los campos `nombre` y `apellido`, normalizando los espacios de unión y conservando nombres compuestos, apellidos y tildes.
- Centralizar los formatos de presentación para utilizarlos de forma consistente en tablas, formularios, mensajes, confirmaciones y documentos.
- Para personas con el mismo nombre, mostrar también el correo en los selectores, dentro de los permisos que ya tienen los administradores.
- Distinguir los estados de carga, error de consulta y nombre no disponible. Un UUID no debe reaparecer como reemplazo del nombre.
- Mantener los UUID como valores internos de selección, relaciones, rutas y solicitudes a la API.
- Conservar los identificadores de negocio legibles: documento de identidad, número de departamento, número de operación bancaria, códigos de concepto, periodos y versiones.
- Sustituir también los UUID recortados que actualmente se utilizan como referencia visual.

## 2. Completar los datos que necesita la interfaz

Existen ubicaciones donde el nombre ya está disponible y otras donde la API devuelve únicamente el identificador de la referencia.

### 2.1. Nombre del condominio en la sesión

Actualizar las respuestas de inicio de sesión y de `/auth/me` para incluir `condominio_nombre`.

Actualmente el backend consulta el nombre al obtener los contextos del usuario, pero lo descarta al construir su perfil. Aprovechar esa información para que Junta, Auditor y Residente puedan mostrar su condominio correctamente.

En una sesión global de SuperAdmin, el contexto de sesión seguirá siendo global; el nombre del condominio de trabajo procederá de su selección activa.

### 2.2. Nombres asociados a operaciones

Enriquecer las respuestas que alimentan referencias visibles con las etiquetas necesarias, por ejemplo:

- Nombre completo de quien aprobó un presupuesto.
- Referencia bancaria de un pago mostrado en el estado de cuenta.
- Nombre del usuario relacionado con una operación cuando corresponda.

Resolver el aprobador también cuando su cuenta esté inactiva o ya no figure en el listado actual de usuarios. Si una referencia histórica o técnica no permite resolver una identidad, presentar un estado legible de información no disponible.

Obtener las etiquetas mediante consultas conjuntas o en lote, evitando una petición adicional por cada fila. Resolverlas sobre los recursos autorizados para el perfil que realiza la consulta.

### 2.3. Búsqueda de personas

Añadir dos búsquedas paginadas para sustituir los campos manuales de UUID:

1. **Usuarios del condominio:** selección de personas para relevos y operaciones contextuales.
2. **Identidades existentes, exclusiva de SuperAdmin:** incorporación de una cuenta que todavía no pertenece al condominio.

Las búsquedas deberán permitir encontrar personas fuera de la primera página del listado y devolver la información necesaria para identificar y seleccionar cada opción.

**Áreas principales del backend:** `src/modules/usuarios/`, respuestas de presupuestos y estado de cuenta, y productores de las salidas afectadas.

## 3. Compartir el condominio activo entre las pantallas

Unificar el contexto activo como **identificador + nombre** para que lo utilicen:

- La cabecera general.
- El portal de Junta.
- Configuración.
- Presupuestos.
- El portal de Residente cuando corresponda.

En SuperAdmin, al seleccionar otro condominio, todas esas zonas deberán reflejar el nuevo nombre.

Limpiar las selecciones y búsquedas dependientes al cambiar de contexto. Una respuesta atrasada del condominio anterior no deberá sobrescribir el nombre ni las opciones del nuevo.

### Archivos principales

- `frontend/src/context/AuthContext.tsx`.
- `frontend/src/lib/session.ts`.
- `frontend/src/components/layout/TopBar.tsx`.
- `frontend/src/features/junta/JuntaPortal.tsx`.
- `frontend/src/app/residente/page.tsx`.

## 4. Sustituir los formularios que exigen UUID

### 4.1. Incorporar un usuario existente

En `frontend/src/features/junta/UsuariosSection.tsx`:

- Reemplazar «UUID del usuario» por un buscador de personas.
- Mostrar nombre completo y correo.
- Mantener la persona seleccionada aunque cambie la página de resultados.
- Enviar internamente su identificador al asignar el acceso.
- Exigir una selección válida; el texto libre de búsqueda no equivale a una persona seleccionada.

### 4.2. Relevar accesos

En `frontend/src/features/junta/RelevosSection.tsx`:

- Reemplazar los campos de usuario saliente y entrante por selectores con búsqueda.
- Mostrar nombres completos en el campo seleccionado.
- Mantener las restricciones actuales de roles, vínculos y unidades.
- Limpiar la unidad seleccionada cuando cambie el usuario saliente.
- Actualizar instrucciones, validaciones y mensajes.

Actualmente las sugerencias de relevo muestran nombres, pero al elegir una insertan el UUID en el campo. Corregir el control completo, no solamente su etiqueta.

### 4.3. Comportamiento compartido de los selectores

- Navegación por teclado y etiquetas accesibles.
- Estados de carga, resultados vacíos y recuperación ante errores.
- Búsqueda paginada que abarque los resultados autorizados.
- Desambiguación de personas con el mismo nombre.
- Limpieza de una selección anterior cuando se modifique el texto para buscar otra persona.
- Selecciones vinculadas al condominio activo.

Actualizar estos flujos junto con la tabla de usuarios para que la incorporación y los relevos tengan un reemplazo funcional del mecanismo de copiar UUID.

## 5. Corregir todas las ubicaciones visibles detectadas

Las rutas de la siguiente tabla son relativas a `frontend/src/`:

| Ubicación | Cambio previsto |
| --- | --- |
| `components/layout/TopBar.tsx` | Nombre completo del usuario y nombre del condominio. |
| `features/junta/JuntaPortal.tsx` | Nombre del condominio activo y confirmaciones con unidades legibles. |
| `features/junta/ConfiguracionCondominio.tsx` | Retirar la línea del UUID y conservar nombre y dirección. |
| `features/junta/UsuariosSection.tsx` | Retirar el UUID bajo el nombre y usar nombres completos en mensajes. |
| `features/junta/RelevosSection.tsx` | Selección de personas por nombre. |
| `features/junta/PresupuestoMensual.tsx` | Condominio por nombre, aprobador por nombre completo y presupuesto identificado por periodo y versión. |
| `features/junta/ConciliacionSection.tsx` | Edificio y departamento en lugar del UUID de la unidad. |
| `features/junta/MorasSection.tsx` | Edificio, departamento y piso. |
| `features/junta/CuotasSection.tsx` | Unificar la identificación de unidades para distinguir números repetidos entre edificios. |
| `components/domain/ResultadoPago.tsx` | Referencia bancaria legible en lugar del UUID del comprobante. |
| `features/residente/EstadoCuenta.tsx` | Sustituir el UUID recortado del pago y su tooltip por una referencia legible. |
| `components/domain/VoucherDownloadButton.tsx` | Fecha y revisión en lugar del fragmento del UUID de evidencia. |
| `features/junta/FondosMorasPanel.tsx` | Código y descripción del concepto, incluyendo sus estados de información faltante. |
| `lib/errors.ts` | Mensajes que indiquen seleccionar un usuario en lugar de pedir su UUID. |

Revisar además títulos, ayudas, placeholders, mensajes de éxito, confirmaciones y etiquetas accesibles.

En las pantallas que ya utilizan nombres correctamente, comprobar que los cambios del contexto y de los contratos mantengan una presentación coherente.

## 6. Corregir correos y archivos descargados

### 6.1. Casos confirmados

- El correo de cambio de acceso imprime el UUID del condominio en `src/modules/usuarios/comunicaciones.py`.
- Los documentos PDF/DOCX de prorrateo imprimen el identificador del aprobador en `src/modules/cuotas/documentos_prorrateo.py`.

Cambiar ambas salidas para mostrar el nombre correspondiente.

### 6.2. Nombres de descarga

Actualizar los nombres de archivos generados o descargados para que utilicen referencias legibles. Ejemplos ilustrativos:

```text
Prorrateo-Villa-Bonita-2026-11-Torre-A-v2.pdf
Voucher-BCP-Operacion-123456.png
```

- Conservar la extensión correspondiente al archivo real.
- Sanear los nombres para que funcionen correctamente como archivos.
- Utilizar los datos reales del condominio, periodo, edificio y comprobante.
- Revisar la generación de nombres tanto en `frontend/src/lib/api.ts` como en las respuestas de descarga del backend.

### 6.3. Contenido generado

Comprobar los mensajes generados de notificaciones y los fallbacks de los documentos donde puedan aparecer referencias técnicas.

La corrección debe realizarse en la fuente de la etiqueta o del mensaje generado, en lugar de aplicar una sustitución indiscriminada de cadenas con formato UUID.

## 7. Actualizar contratos y documentación

Actualizar conjuntamente:

- Los esquemas y ejemplos de OpenAPI afectados en `specs/03-contracts/openapi/`.
- Los tipos de `frontend/src/lib/api.ts`.
- Los escenarios de aceptación de búsquedas y selección.
- La documentación de contratos correspondiente en `specs/05-api/`.
- `frontend/DESIGN.md`, que actualmente documenta mostrar el identificador cuando falta el nombre del condominio.

Los campos nuevos serán adicionales a los identificadores existentes, conservando la compatibilidad de las operaciones.

Mantener separadas las etiquetas de presentación de los datos utilizados para persistencia, auditoría, autorización e idempotencia.

## 8. Verificar el resultado completo

### 8.1. Funcionamiento

- Buscar personas por nombre y apellido.
- Seleccionar personas que no estén en la primera página.
- Distinguir homónimos.
- Incorporar usuarios existentes y completar relevos.
- Cambiar de condominio y recargar la página.
- Consultar presupuestos aprobados por usuarios históricos.

### 8.2. Presentación

- Comprobar nombres largos, compuestos y con tildes.
- Revisar pantallas móviles y navegación por teclado.
- Verificar la ausencia de UUID en textos, tooltips y campos visibles de selección.
- Comprobar documentos y descargas con referencias legibles.
- Distinguir carga, error e información no disponible.
- Verificar también las referencias recortadas de UUID.

### 8.3. Integración

- Las operaciones envían el identificador de la persona realmente seleccionada.
- Cada perfil obtiene nombres únicamente de los recursos que puede consultar.
- Los cambios de contexto mantienen separados los datos de cada condominio.
- Las respuestas atrasadas no restauran nombres u opciones del contexto anterior.
- Los departamentos con el mismo número en diferentes edificios siguen siendo seleccionables sin ambigüedad.
- Los saldos, importes, roles, vínculos e idempotencia mantienen su comportamiento.

### 8.4. Comprobaciones técnicas

Ejecutar las pruebas pertinentes de frontend, backend y contratos, junto con tipos, lint y compilación.

Reutilizar y ampliar las suites existentes de presentación, sesión, cliente API, identidad, aislamiento entre condominios, estado de cuenta y documentos de prorrateo.

En `frontend/`, las comprobaciones previstas son:

```bash
node --test tests/*.test.mjs
npm run lint
npx --no-install tsc --noEmit
npm run build
```

Las pruebas PostgreSQL utilizarán una conexión exclusiva de pruebas mediante `CON13_TEST_DATABASE_URL` y las variables específicas que requiera cada suite.

## 9. Orden de ejecución y actualización de servicios

1. Actualizar contratos y completar los datos necesarios.
2. Unificar el contexto compartido y los formatos de presentación.
3. Implementar los buscadores y sustituir los campos manuales de UUID.
4. Actualizar las pantallas y mensajes afectados.
5. Corregir correos, documentos y nombres de descarga.
6. Ejecutar las verificaciones y actualizar la documentación.
7. Reconstruir los servicios una vez implementado y verificado el cambio.

Desde la raíz del proyecto, la actualización de los servicios se realizará con:

```bash
docker compose up -d --build
```

## Criterios de finalización

- [ ] Las personas se presentan por nombre y apellido completos.
- [ ] Los condominios se presentan por su nombre registrado.
- [ ] Incorporar usuarios y realizar relevos no requiere conocer ni pegar UUID.
- [ ] Los selectores permiten buscar más allá de la primera página y distinguir homónimos.
- [ ] Los nombres del contexto son coherentes entre cabecera, Junta, configuración y presupuesto.
- [ ] Las referencias de unidades, presupuestos, comprobantes, evidencias y conceptos son legibles.
- [ ] Los estados de carga, error y datos faltantes no muestran UUID como fallback.
- [ ] Correos, documentos y descargas utilizan nombres y referencias legibles.
- [ ] Las operaciones mantienen sus identificadores internos y los permisos existentes.
- [ ] Los contratos, tipos y documentación reflejan los cambios.
- [ ] Las verificaciones pertinentes de funcionamiento, presentación e integración son satisfactorias.

**El cambio estará terminado cuando se puedan realizar los flujos habituales reconociendo a las personas y condominios por sus nombres, sin necesitar conocer ni pegar sus UUID.**
