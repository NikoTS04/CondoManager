# DESIGN.md — Diseño del frontend de CondoManager

> **Estado:** Propuesta para aprobación · **Alcance:** `frontend/` (Next.js 14 App Router, TypeScript, Tailwind 3, lucide-react)
> Este documento es la fuente de verdad visual y de interacción. Todo componente nuevo debe cumplirlo; los existentes se alinean por fases (§12).

## 1. Propósito y principios

CondoManager maneja **dinero y accesos** de una comunidad. La interfaz debe transmitir una sola cosa: *"puedes confiar en lo que ves"*.

1. **Claridad antes que decoración.** Lo primero que ve cada rol es lo que debe hacer o lo que debe (monto, vencimiento, estado). Nada de hero banners en pantallas de trabajo.
2. **El estado financiero nunca es ambiguo.** Cada monto muestra moneda, dos decimales y estado en texto + icono + color (nunca solo color).
3. **Mobile-first para residentes, denso para la junta.** El residente paga y reserva desde el celular (Yape/Plin); la junta concilia y revisa en escritorio.
4. **Seguro por defecto en la UI.** La interfaz refleja permisos, pero **nunca los decide**: ocultar un botón no es seguridad; el backend siempre valida.
5. **Errores que ayudan.** Dicen qué pasó, por qué y qué hacer, en español, con el `error_code` del backend como referencia.
6. **Un solo sistema.** Mismos tokens, mismos componentes, mismas reglas de formulario en todas las pantallas.

## 2. Usuarios y contextos

| Rol (backend) | Dispositivo principal | Tareas clave | Portal |
|---|---|---|---|
| `PROPIETARIO`, `INQUILINO` | Móvil | Ver cuotas y saldo, reportar pago con voucher, reservar áreas, ver notificaciones | **Residente** |
| `ADMIN_JUNTA` / administrador, tesorero | Escritorio | Presupuesto, emisión, bandeja de conciliación, moras, comunicados | **Junta** |
| `AUDITOR` | Escritorio | Consulta de solo lectura, bitácora | **Junta** (modo lectura) |
| `SUPERADMIN` | Escritorio | Crear/configurar condominios | **Junta** + Configuración |

Contexto siempre visible: **condominio activo**, **usuario/rol** y, en el residente, **departamento activo**.

## 3. Arquitectura de información

```
/login
/                      → redirige según rol (residente → /residente, junta → /junta)
/residente             (móvil primero)
   ├─ Resumen          saldo, próxima cuota, estado de solvencia
   ├─ Cuotas           historial y detalle de cada periodo
   ├─ Pagos            reportar pago · estado de comprobantes
   ├─ Reservas         áreas, calendario, mis reservas
   └─ Avisos           notificaciones
/junta                 (escritorio primero)
   ├─ Resumen          KPIs: recaudación, morosidad, pendientes de conciliar
   ├─ Estructura       edificios y departamentos (importar CSV)
   ├─ Presupuesto      presupuesto del periodo y método de distribución
   ├─ Cuotas           emisión y estado por departamento
   ├─ Conciliación     bandeja de comprobantes
   ├─ Reservas         vista de la junta
   ├─ Comunicados      envío y bitácora
   └─ Auditoría        bitácora inmutable (solo lectura)
/configuracion         condominio (SUPERADMIN)
```

Navegación: **barra superior** (marca, condominio, usuario) + **navegación de sección** propia de cada portal:
- Residente móvil: *bottom tab bar* de 4 ítems (Resumen, Pagos, Reservas, Avisos).
- Junta escritorio: *sidebar* colapsable a la izquierda. En tablet se reduce a iconos.

El selector de "perfiles de demostración" del `Navbar` actual se mueve a un panel visible solo con `NEXT_PUBLIC_DEMO_MODE=true`.

## 4. Fundamentos visuales (design tokens)

Los tokens viven en `tailwind.config.ts` (`theme.extend`) y `globals.css` (variables CSS). **No se usan colores arbitrarios** (`bg-[#…]`).

### 4.1 Color

Se conserva la identidad actual (verde marca sobre neutros slate) y se asignan **roles semánticos** para dejar de decidir color por pantalla.

| Token | Valor | Uso |
|---|---|---|
| `brand-600` / `brand-700` | `#16a34a` / `#15803d` | Acción primaria, enlaces de marca |
| `brand-50` / `100` | `#f0fdf4` / `#dcfce7` | Fondos suaves de éxito/selección |
| `ink` (slate-900) | `#0f172a` | Texto principal, barra superior |
| `muted` (slate-500/600) | `#64748b` / `#475569` | Texto secundario (≥ 4.5:1 sobre blanco; usar 600 para texto pequeño) |
| `line` (slate-200) | `#e2e8f0` | Bordes y separadores |
| `surface` / `canvas` | `#ffffff` / `#f8fafc` | Tarjetas / fondo de página (fondo plano, sin gradiente) |
| `success` | emerald 600 / 50 | Pagado, al día, aprobado |
| `warning` | amber 600 / 50 | Pendiente, en revisión, por vencer |
| `danger` | rose 600 / 50 | Vencida, en mora, rechazado, errores |
| `info` | blue 600 / 50 | Informativo, acciones de la junta |
| `audit` | violet 600 / 50 | Modo auditor (solo lectura) |

Reglas:
- **Un color = un significado.** El azul de "Junta" y el violeta de "Auditor" identifican *rol*, no estados. Los estados usan solo success/warning/danger/info.
- Contraste mínimo **WCAG AA** (4.5:1 texto, 3:1 componentes y foco).
- Modo oscuro: **fuera de alcance** por ahora; los tokens están como variables CSS para habilitarlo después.

### 4.2 Tipografía

- Familia: **Inter** (vía `next/font`, subset latin) con *fallback* al stack del sistema. Cifras **tabulares** (`font-variant-numeric: tabular-nums`) en toda tabla y monto.

| Estilo | Clase | Uso |
|---|---|---|
| Título de página | `text-2xl font-bold` (móvil) / `text-3xl` (≥ lg) | Un `h1` por página |
| Sección | `text-lg font-semibold` | `h2` |
| Subsección | `text-base font-semibold` | `h3` |
| Cuerpo | `text-sm` / `text-base` en móvil | Texto general (≥ 16 px en inputs móviles para evitar zoom) |
| Apoyo | `text-xs text-muted` | Ayudas, metadatos. Nunca para información crítica |
| Monto destacado | `text-3xl font-bold tabular-nums` | Saldo, total a pagar |

Se elimina `font-black` y el texto con degradado de la marca.

### 4.3 Espaciado, forma y elevación

- Escala de 4 px (Tailwind). Separación entre secciones `space-y-6`; dentro de tarjeta `p-4 sm:p-6`.
- Radios: **`rounded-lg`** (controles), **`rounded-xl`** (tarjetas y paneles), `rounded-full` (chips y avatares). Se retira `rounded-2xl` salvo diálogos.
- Elevación: tarjetas con **borde `line` y sombra `shadow-sm`**; solo menús, popovers y diálogos usan `shadow-lg`.
- Ancho máximo de contenido: `max-w-7xl`; formularios `max-w-xl`; lectura `max-w-prose`.

### 4.4 Iconografía y movimiento

- Solo **lucide-react**, 16 px en línea con texto y 20 px en botones/nav, `aria-hidden` cuando acompañan texto.
- Transiciones de 150 ms (`transition-colors`) en hover/foco; respetar `prefers-reduced-motion` (sin animaciones de entrada ni *skeleton shimmer*).

## 5. Dinero, fechas y datos (reglas obligatorias)

1. **Nunca `Number`/`float` para dinero.** Los montos viajan como **string decimal** (`"1250.50"`) tal como los entrega la API. Para operar en cliente se usa `decimal.js` (o se deja que el backend calcule). Hoy `PresupuestoMensual.tsx` usa `Number(montoTotal)`; es una violación del ADR-002 y debe corregirse.
2. Formato único mediante `lib/format.ts`: `formatMoney("1250.5", "PEN")` → `S/ 1,250.50` (`es-PE`, 2 decimales fijos, símbolo según moneda del condominio). Alineados a la derecha en tablas.
3. Coeficientes con 4 decimales (`12.3456 %`); la suma esperada `100.0000 %` se muestra con indicador *cumple / no cumple*.
4. Fechas: `lib/format.ts` → `formatDate` (`08 oct 2026`), periodos `YYYY-MM` mostrados como `Octubre 2026`. Zona horaria del condominio (`America/Lima`).
5. Los `error_code` del backend se mapean a mensajes en un único diccionario (`lib/errors.ts`), con *fallback* genérico.

## 6. Componentes del sistema

Se crea `src/components/ui/` con primitivas **propias y sin dependencia nueva obligatoria** (opcional: Radix UI para accesibilidad de diálogos/menús). Cada componente se documenta con sus variantes en este archivo.

### 6.1 Primitivas

| Componente | Variantes / estados | Notas |
|---|---|---|
| `Button` | `primary` (brand), `secondary` (borde), `danger`, `ghost`; `sm/md/lg`; `loading`, `disabled` | Alto mínimo 44 px en móvil; icono opcional; `loading` deshabilita y muestra spinner con texto accesible |
| `Input`, `Select`, `Textarea`, `Checkbox`, `Radio` | `default`, `error`, `disabled` | Siempre con `Label` asociada, ayuda opcional y mensaje de error enlazado con `aria-describedby` |
| `MoneyInput` | — | Teclado numérico (`inputMode="decimal"`), entrada y salida como string, prefijo de moneda |
| `FileDropzone` | `idle`, `dragover`, `error`, `uploaded` | Para vouchers: PNG/JPG/PDF, límite de tamaño visible, vista previa, alternativa por botón (no solo arrastrar) |
| `Card` | `default`, `interactive` | Encabezado + contenido + pie |
| `Badge` / `StatusChip` | success, warning, danger, info, neutral | **Icono + texto + color** |
| `Alert` | success, warning, danger, info | `role="alert"` para errores, `role="status"` para éxitos; descartable solo si no es crítico |
| `Tabs` | — | Patrón ARIA tabs, navegable con flechas |
| `Dialog` / `ConfirmDialog` | — | Foco atrapado, `Esc` cierra, devuelve foco; confirmaciones de acciones financieras |
| `Toast` | — | Solo confirmaciones no críticas; los errores permanecen en pantalla |
| `Skeleton`, `Spinner` | — | Carga |
| `EmptyState` | — | Icono + explicación + acción sugerida |

### 6.2 Compuestos de dominio

| Componente | Descripción |
|---|---|
| `MoneyAmount` | Muestra un monto formateado; prop `tone` para negativo/positivo |
| `CuotaStatusChip` | `EMITIDA`, `PENDIENTE`, `PAGO_PARCIAL`, `PAGADA`, `VENCIDA`, `EN_MORA` → color/icono/etiqueta |
| `ComprobanteStatusChip` | `EN_REVISION` (warning), `APROBADO` (success), `RECHAZADO` (danger) |
| `SolvenciaBanner` | Estado de solvencia del departamento; si está bloqueado explica el motivo y el paso para desbloquear |
| `DataTable` | Cabecera fija, orden, filtros, paginación, selección de fila; en móvil se transforma en lista de tarjetas |
| `PeriodPicker` | Selector `YYYY-MM` accesible |
| `PageHeader` | Título, descripción, acciones primarias, breadcrumb |
| `ConfirmFinancialAction` | Diálogo que repite el monto e impacto antes de aprobar/rechazar/emitir |

## 7. Patrones de interacción

### 7.1 Formularios
- Validación en cliente **espejo** de la del backend (formato, rangos); el backend es la autoridad. Se valida al salir del campo y al enviar; el primer error recibe el foco.
- Botón de envío deshabilitado solo durante el envío (no mientras el formulario está incompleto).
- Errores del servidor (`422`, `409`…) se muestran en un `Alert` superior y, si el backend indica campo, junto al campo.
- Acciones irreversibles o financieras (aprobar presupuesto, emitir cuotas, aprobar comprobante) requieren `ConfirmFinancialAction`.

### 7.2 Carga, vacío y error (toda vista de datos define los tres)
- **Cargando:** skeleton con la forma del contenido final (sin saltos de layout).
- **Vacío:** `EmptyState` con acción.
- **Error:** `Alert` con mensaje, `error_code` colapsable y botón *Reintentar*.
- Datos de servidor con **TanStack Query** (caché, reintentos, invalidación tras mutaciones) en lugar de `useEffect` + estado manual.

### 7.3 Flujos principales

**Reportar pago (residente, móvil):** Pagos → *Reportar pago* → departamento (preseleccionado) · banco · n.º de operación · fecha · monto · voucher → revisión del resumen → enviar → pantalla de confirmación "Recibimos tu comprobante, estado: **En revisión**" (respuesta `202`). Si el backend responde `VOUCHER_EN_EVALUACION` se muestra el registro previo; si `VOUCHER_YA_CONCILIADO`, un `Alert` informativo con la fecha de aprobación.

**Conciliar (junta, escritorio):** bandeja con filtros por estado/fecha/banco; panel de detalle a la derecha con voucher y datos; acciones *Aprobar* / *Rechazar* (motivo obligatorio) con confirmación. Teclado: `↑/↓` navegar, `A` aprobar, `R` rechazar.

**Presupuesto → emisión (junta):** asistente de 3 pasos visible en `Presupuesto` y `Cuotas`: 1) presupuesto aprobado, 2) método de distribución (validación `100.0000 %` en vivo), 3) emitir. Cada paso muestra su estado y bloquea el siguiente con explicación si falta algo (refleja el bloqueo del backend sin sustituirlo).

**Reservar (residente):** elegir área → fecha → franja; si hay mora activa se muestra `SolvenciaBanner` con el monto vencido y el acceso directo a *Reportar pago* en lugar de un error genérico `403`.

### 7.4 Estados de sesión y permisos
- Sesión expirada (`TOKEN_EXPIRADO`) → redirección a `/login` conservando la ruta de retorno.
- `RoleGuard` evita renderizar secciones no permitidas, pero toda llamada sigue protegida por el backend; un `403` muestra una página "Sin acceso" explicativa.
- Modo auditor: controles de escritura **ausentes** (no deshabilitados), banner violeta "Solo lectura".

## 8. Diseño responsivo

| Breakpoint | Layout |
|---|---|
| `< 640` (móvil) | Una columna, bottom tab bar (residente), tablas → tarjetas, objetivos táctiles ≥ 44×44 px |
| `640–1023` (tablet) | Dos columnas donde aporte, sidebar en iconos |
| `≥ 1024` (escritorio) | Sidebar completo (junta), tablas completas, panel de detalle lateral |

Reglas: sin scroll horizontal de página; las tablas anchas se desplazan dentro de su contenedor con indicación; `100dvh` en lugar de `100vh`; probar en 360 px de ancho como mínimo.

## 9. Accesibilidad (objetivo WCAG 2.2 AA)

- Estructura semántica: `header`, `nav`, `main`, un solo `h1`, jerarquía sin saltos, `lang="es"`.
- Enlace "Saltar al contenido" al inicio.
- Todo interactivo operable con teclado; **foco visible** (`focus-visible:ring-2 ring-brand-600 ring-offset-2`), orden lógico, sin trampas salvo diálogos.
- Etiquetas para todo control; icon-buttons con `aria-label`. (Hoy hay solo 8 atributos ARIA en ~3,900 líneas.)
- Estado nunca solo por color; tablas con `<th scope>` y `<caption>` (puede ser `sr-only`).
- Mensajes dinámicos anunciados (`role="status"` / `role="alert"`, `aria-live`).
- Objetivos táctiles ≥ 44 px; zoom hasta 200 % sin pérdida de funcionalidad.
- Verificación: `eslint-plugin-jsx-a11y` en CI, `axe` en pruebas de componentes, revisión manual con teclado y lector de pantalla en los flujos §7.3.

## 10. Contenido y tono

- Español neutro, tuteo en el portal del residente ("Tu saldo"), tratamiento neutro-formal en la junta ("Aprobar presupuesto").
- Botones con verbo + objeto: *Reportar pago*, *Aprobar comprobante*. Evitar "Aceptar/OK".
- Terminología del [lenguaje ubicuo](../specs/00-core/ubiquitous-language.md): *cuota*, *alícuota*, *saldo a favor*, *conciliación*, *solvencia*, *mora*. Sin jerga técnica en la UI (no "403", no "idempotencia"; el código va como detalle secundario).
- Mensajes de error: **qué pasó + por qué + qué hacer**. Ej.: "No pudimos reservar el salón: tienes una cuota vencida de S/ 141.78. Reporta tu pago para desbloquear las reservas."

## 11. Arquitectura técnica del frontend

```
src/
  app/                      # rutas (App Router); páginas finas
    (auth)/login
    (residente)/residente/...
    (junta)/junta/...
    layout.tsx · error.tsx · not-found.tsx · loading.tsx
  components/
    ui/                     # primitivas (§6.1)
    domain/                 # compuestos (§6.2)
    layout/                 # AppShell, Sidebar, BottomNav, TopBar
  features/<dominio>/       # componentes + hooks + esquemas por dominio
    cuotas/ pagos/ reservas/ condominios/ notificaciones/ auditoria/
  lib/
    api/                    # cliente HTTP único, errores tipados, un archivo por dominio
    format.ts · errors.ts · money.ts
  context/                  # Auth (sesión real) — sin lógica de negocio
```

Decisiones:
- **Cliente API único** (`lib/api/client.ts`): adjunta Bearer, normaliza el formato de error `{error_code, mensaje, detalles}`, maneja 401 globalmente. **Se eliminan los datos y respuestas simuladas** de `api.ts` (552 líneas con mocks y personas demo) a medida que cada endpoint exista; hasta entonces, los mocks quedan tras `NEXT_PUBLIC_USE_MOCKS`.
- **Tipos generados** desde el OpenAPI (`specs/03-contracts/openapi/condomanager.openapi.yaml`) con `openapi-typescript`, en lugar de interfaces escritas a mano.
- **Server Components** por defecto; `"use client"` solo donde hay interacción. Páginas grandes (`junta/page.tsx` 746 líneas, `residente/page.tsx` 711) se dividen por pestaña/feature.
- **Estado de servidor:** TanStack Query. **Formularios:** React Hook Form + Zod (esquemas espejo del contrato).
- **Pruebas:** Vitest + Testing Library (componentes y formateo de dinero), Playwright para los flujos de §7.3, `axe` para accesibilidad.
- **Calidad en CI:** `tsc --noEmit`, `next lint` (con `jsx-a11y`), pruebas y `next build`.

## 12. Plan de adopción

Cada fase es un PR pequeño que mantiene la app funcionando.

| Fase | Contenido |
|---|---|
| **F0 – Fundamentos** | Tokens en Tailwind, Inter, `lib/format.ts` (dinero/fechas), `ui/` base (Button, Input, Card, Badge, Alert), foco visible, "Saltar al contenido" |
| **F1 – Shell** | `AppShell` con sidebar (junta) y bottom nav (residente); modo demo detrás de variable de entorno; páginas `error`/`not-found`/`loading` |
| **F2 – Datos** | Cliente API único, TanStack Query, tipos desde OpenAPI, `lib/errors.ts` |
| **F3 – Formularios** | RHF + Zod, `MoneyInput`, `FileDropzone`; corregir `Number()` en `PresupuestoMensual` |
| **F4 – Pantallas por historia** | Presupuesto/distribución (CON-9/10), emisión y saldo a favor (CON-11/13), reporte de comprobante (CON-22/23), estructura (CON-3), configuración (CON-2) |
| **F5 – Calidad** | Vitest, Playwright, axe, CI |
| **F6 – Junta/Residente completos** | Conciliación con atajos, calendario de reservas, bitácora de auditoría |

## 13. Estado actual vs. objetivo (brecha)

| Aspecto | Hoy | Objetivo |
|---|---|---|
| Estilos | Clases Tailwind repetidas en cada vista; colores por pantalla (emerald/blue/purple/rose) | Tokens y componentes `ui/` reutilizados |
| Dinero | `Number()` en formularios, formato manual | String decimal + `formatMoney` |
| Datos | Mocks y personas demo mezclados en `lib/api.ts` | Cliente único + tipos OpenAPI; mocks aislados |
| Estructura | Páginas de 700+ líneas | Páginas finas + features |
| Accesibilidad | Pocos atributos ARIA, foco por defecto | WCAG 2.2 AA con verificación automática |
| Navegación | Navbar única con selector de perfiles | AppShell por portal, modo demo opcional |
| Móvil | Responsive básico | Mobile-first real (bottom nav, tablas → tarjetas) |

## 14. Decisiones abiertas

1. ¿Adoptar **shadcn/ui + Radix** (menos código propio, ya mencionado en `tech-stack.md`) o primitivas propias? *Recomendado: Radix para Dialog/Menu/Tabs, estilos propios.*
2. ¿Se añade **modo oscuro** en este ciclo o se difiere?
3. ¿Mantener el **verde actual** como color de marca o rediseñar identidad?
4. ¿Se mantiene el **modo demo** (perfiles simulados) para las presentaciones de la universidad?
5. ¿La **Junta** y el **Auditor** comparten portal (propuesto) o el auditor tiene portal separado?
