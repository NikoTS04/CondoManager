# Modelo de Dominio y Esquema de Entidades (Domain Entities)

## 1. Diagrama Conceptual de Entidades

```
  [ Condominio ] (1)
        │
        ├──▶ [ Edificio / Torre ] (1..N)
        │            │
        │            └──▶ [ Departamento / Unidad ] (1..N)
        │                         │
        │                         ├──▶ [ CuotaMantenimiento ] (1..N)
        │                         │            │
        │                         │            └──▶ [ DetalleConcepto ] (1..N)
        │                         │
        │                         ├──▶ [ ComprobantePago ] (1..N)
        │                         │            │
        │                         │            └──▶ [ ImputacionPago ] (1..N)
        │                         │
        │                         └──▶ [ ReservaArea ] (1..N)
        │
        ├──▶ [ AreaComun ] (1..N) ──▶ [ ReservaArea ]
        │
        ├──▶ [ Proveedor ] (1..N) ──▶ [ ContratoProveedor ] (1..N) ──▶ [ GastoEgreso ] (1..N)
        │
        └──▶ [ TicketIncidencia ] (1..N)
```

---

## 2. Definición Detallada de Tablas / Entidades

### 2.1 Estructura Inmobiliaria
- **`condominios`**: `id (UUID)`, `nombre (VARCHAR)`, `direccion (TEXT)`, `moneda (VARCHAR(3))`, `regla_mora_tipo (VARCHAR)`, `tasa_mora (NUMERIC(6,4))`, `dias_corte (INT)`, `dias_gracia (INT)`.
- **`edificios`**: `id (UUID)`, `condominio_id (FK)`, `nombre_bloque (VARCHAR)`, `total_pisos (INT)`.
- **`departamentos`**: `id (UUID)`, `edificio_id (FK)`, `numero (VARCHAR)`, `piso (INT)`, `coeficiente_participacion (NUMERIC(6,4))`, `saldo_a_favor (NUMERIC(12,2))`, `estado_financiero (VARCHAR: AL_DIA, OBSERVADO, EN_MORA)`.

### 2.2 Usuarios y Seguridad
- **`usuarios`**: `id (UUID)`, `email (VARCHAR UNIQUE)`, `password_hash (VARCHAR)`, `nombre (VARCHAR)`, `apellido (VARCHAR)`, `telefono (VARCHAR)`, `documento_identidad (VARCHAR)`.
- **`usuario_departamentos`**: `id (UUID)`, `usuario_id (FK)`, `departamento_id (FK)`, `tipo_relacion (VARCHAR: PROPIETARIO_TITULAR, INQUILINO, COPROPIETARIO)`, `es_activo (BOOLEAN)`.
- **`usuario_roles`**: `usuario_id (FK)`, `condominio_id (FK)`, `rol (VARCHAR: ADMIN_JUNTA, AUDITOR, RESIDENTE)`.

### 2.3 Finanzas y Recaudación
- **`cuotas_mantenimiento`**: `id (UUID)`, `departamento_id (FK)`, `periodo (VARCHAR: 2026-10)`, `monto_ordinario (NUMERIC(12,2))`, `monto_extraordinario (NUMERIC(12,2))`, `monto_mora (NUMERIC(12,2))`, `monto_descuento (NUMERIC(12,2))`, `monto_total_exigible (NUMERIC(12,2))`, `monto_pagado (NUMERIC(12,2))`, `fecha_emision (DATE)`, `fecha_vencimiento (DATE)`, `estado (VARCHAR: EMITIDA, PENDIENTE, PAGO_PARCIAL, PAGADA, VENCIDA, EN_MORA)`.
- **`comprobantes_pago`**: `id (UUID)`, `departamento_id (FK)`, `usuario_id (FK)`, `banco_origen (VARCHAR)`, `numero_operacion (VARCHAR)`, `fecha_operacion (DATE)`, `monto (NUMERIC(12,2))`, `url_imagen_voucher (TEXT)`, `idempotency_hash (VARCHAR UNIQUE)`, `estado (VARCHAR: EN_REVISION, APROBADO, RECHAZADO)`, `motivo_rechazo (TEXT)`, `conciliado_por (FK usuario)`, `conciliado_en (TIMESTAMP)`.
- **`imputaciones_pago`**: `id (UUID)`, `comprobante_id (FK)`, `cuota_id (FK)`, `monto_aplicado (NUMERIC(12,2))`, `fecha_imputacion (TIMESTAMP)`.

### 2.4 Áreas Comunes
- **`areas_comunes`**: `id (UUID)`, `condominio_id (FK)`, `nombre (VARCHAR)`, `descripcion (TEXT)`, `aforo_maximo (INT)`, `costo_reserva (NUMERIC(12,2))`, `tiempo_maximo_horas (INT)`, `esta_activa (BOOLEAN)`.
- **`reservas`**: `id (UUID)`, `area_id (FK)`, `departamento_id (FK)`, `usuario_id (FK)`, `fecha_reserva (DATE)`, `hora_inicio (TIME)`, `hora_fin (TIME)`, `estado (VARCHAR: SOLICITADA, CONFIRMADA, RECHAZADA, CANCELADA, COMPLETADA)`, `motivo_rechazo (TEXT)`.

### 2.5 Proveedores, Egresos y Tickets
- **`proveedores`**: `id (UUID)`, `condominio_id (FK)`, `ruc (VARCHAR(11))`, `razon_social (VARCHAR)`, `rubro (VARCHAR)`, `contacto_nombre (VARCHAR)`, `contacto_telefono (VARCHAR)`, `contacto_email (VARCHAR)`.
- **`contratos_proveedor`**: `id (UUID)`, `proveedor_id (FK)`, `fecha_inicio (DATE)`, `fecha_fin (DATE)`, `monto_mensual (NUMERIC(12,2))`, `url_archivo_pdf (TEXT)`, `alerta_60_enviada (BOOLEAN)`, `alerta_30_enviada (BOOLEAN)`.
- **`gastos_egresos`**: `id (UUID)`, `condominio_id (FK)`, `proveedor_id (FK nullable)`, `categoria (VARCHAR)`, `descripcion (TEXT)`, `monto (NUMERIC(12,2))`, `fecha_pago (DATE)`, `nro_factura (VARCHAR)`, `comprobante_url (TEXT)`.
- **`tickets_incidencias`**: `id (UUID)`, `condominio_id (FK)`, `departamento_id (FK)`, `titulo (VARCHAR)`, `descripcion (TEXT)`, `urgencia (VARCHAR: BAJA, MEDIA, ALTA, URGENTE)`, `estado (VARCHAR: REGISTRADO, ASIGNADO, EN_PROCESO, RESUELTO, CERRADO)`, `proveedor_asignado_id (FK nullable)`.

### 2.6 Trazabilidad y Comunicaciones
- **`auditoria_logs`**: `id (UUID)`, `condominio_id (FK)`, `departamento_id (FK nullable)`, `timestamp (TIMESTAMP TZ)`, `accion_ejecutada (VARCHAR)`, `motivo (TEXT)`, `resultado (VARCHAR)`, `actor_tipo (VARCHAR)`, `actor_id (VARCHAR)`, `estado_anterior (JSONB)`, `estado_posterior (JSONB)`, `hash_actual (VARCHAR)`, `hash_previo (VARCHAR)`.
- **`notificaciones_logs`**: `id (UUID)`, `condominio_id (FK)`, `departamento_id (FK)`, `tipo_evento (VARCHAR)`, `canal (VARCHAR)`, `destinatario (VARCHAR)`, `estado (VARCHAR: EN_COLA, ENTREGADO, REINTENTANDO, FALLIDO)`, `intentos (INT)`, `fecha_envio (TIMESTAMP)`.
