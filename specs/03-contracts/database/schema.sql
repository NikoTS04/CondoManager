-- Esquema DDL Formal de Referencia en PostgreSQL 16 para CondoManager (SDD)
-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- 1. Tabla de Condominios
CREATE TABLE condominios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(150) NOT NULL,
    direccion TEXT NOT NULL,
    moneda VARCHAR(3) NOT NULL DEFAULT 'PEN' CHECK (moneda IN ('PEN', 'USD')),
    regla_mora_tipo VARCHAR(20) NOT NULL CHECK (regla_mora_tipo IN ('MONTO_FIJO', 'PORCENTAJE_SALDO')),
    monto_mora_fijo NUMERIC(12,2) CHECK (monto_mora_fijo >= 0.00),
    tasa_mora_porcentaje NUMERIC(7,4) CHECK (tasa_mora_porcentaje BETWEEN 0.0000 AND 100.0000),
    dia_vencimiento SMALLINT NOT NULL CHECK (dia_vencimiento BETWEEN 1 AND 28),
    dias_gracia SMALLINT NOT NULL CHECK (dias_gracia BETWEEN 0 AND 30),
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    CONSTRAINT ck_condominio_configuracion_mora CHECK (
        (regla_mora_tipo = 'MONTO_FIJO'
            AND monto_mora_fijo IS NOT NULL
            AND tasa_mora_porcentaje IS NULL)
        OR
        (regla_mora_tipo = 'PORCENTAJE_SALDO'
            AND tasa_mora_porcentaje IS NOT NULL
            AND monto_mora_fijo IS NULL)
    )
);

-- 2. Tabla de Presupuestos Mensuales (CON-9)
CREATE TABLE presupuestos_mensuales (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    periodo VARCHAR(7) NOT NULL,
    moneda VARCHAR(3) NOT NULL CHECK (moneda IN ('PEN', 'USD')),
    monto_total NUMERIC(12,2) NOT NULL CHECK (monto_total > 0.00),
    fecha_vencimiento DATE NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'BORRADOR'
        CHECK (estado IN ('BORRADOR', 'APROBADO')),
    creado_por VARCHAR(100) NOT NULL,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    aprobado_por VARCHAR(100),
    aprobado_en TIMESTAMP WITH TIME ZONE,
    actualizado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    CONSTRAINT uq_presupuesto_condominio_periodo UNIQUE (condominio_id, periodo),
    CONSTRAINT ck_presupuesto_periodo CHECK (
        periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
    ),
    CONSTRAINT ck_presupuesto_vencimiento_periodo CHECK (
        CASE
            WHEN periodo ~ '^[0-9]{4}-(0[1-9]|1[0-2])$' THEN
                EXTRACT(YEAR FROM fecha_vencimiento) =
                    CAST(SUBSTRING(periodo FROM 1 FOR 4) AS INTEGER)
                AND EXTRACT(MONTH FROM fecha_vencimiento) =
                    CAST(SUBSTRING(periodo FROM 6 FOR 2) AS INTEGER)
            ELSE FALSE
        END
    ),
    CONSTRAINT ck_presupuesto_aprobacion CHECK (
        (estado = 'BORRADOR' AND aprobado_por IS NULL AND aprobado_en IS NULL)
        OR
        (estado = 'APROBADO' AND aprobado_por IS NOT NULL AND aprobado_en IS NOT NULL)
    )
);

-- La coincidencia entre presupuestos_mensuales.moneda y condominios.moneda,
-- así como la inmutabilidad de un presupuesto aprobado, se validan en el servicio.

-- 3. Tabla de Departamentos / Unidades
CREATE TABLE departamentos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE CASCADE,
    numero VARCHAR(20) NOT NULL,
    piso SMALLINT NOT NULL CHECK (piso >= 1),
    coeficiente_participacion NUMERIC(7,4) NOT NULL CHECK (coeficiente_participacion > 0.0000),
    saldo_a_favor NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (saldo_a_favor >= 0.00),
    estado_financiero VARCHAR(20) NOT NULL DEFAULT 'AL_DIA' CHECK (estado_financiero IN ('AL_DIA', 'OBSERVADO', 'EN_MORA')),
    CONSTRAINT uq_condominio_departamento UNIQUE (condominio_id, numero)
);

-- 4. Tabla de Cuotas de Mantenimiento (Anderson - PROC-01)
CREATE TABLE cuotas_mantenimiento (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    departamento_id UUID NOT NULL REFERENCES departamentos(id) ON DELETE RESTRICT,
    periodo VARCHAR(7) NOT NULL,
    monto_ordinario NUMERIC(12,2) NOT NULL CHECK (monto_ordinario >= 0.00),
    monto_extraordinario NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (monto_extraordinario >= 0.00),
    monto_mora NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (monto_mora >= 0.00),
    monto_descuento NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (monto_descuento >= 0.00),
    monto_total_exigible NUMERIC(12,2) NOT NULL CHECK (monto_total_exigible >= 0.00),
    monto_pagado NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (monto_pagado BETWEEN 0.00 AND monto_total_exigible),
    fecha_emision DATE NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'EMITIDA' CHECK (estado IN ('EMITIDA', 'PENDIENTE', 'PAGO_PARCIAL', 'PAGADA', 'VENCIDA', 'EN_MORA')),
    CONSTRAINT uq_departamento_periodo UNIQUE (departamento_id, periodo)
);

-- 5. Tabla de Comprobantes de Pago (Tarqui - PROC-02)
CREATE TABLE comprobantes_pago (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    departamento_id UUID NOT NULL REFERENCES departamentos(id) ON DELETE RESTRICT,
    banco_origen VARCHAR(30) NOT NULL,
    numero_operacion VARCHAR(50) NOT NULL,
    fecha_operacion DATE NOT NULL,
    monto NUMERIC(12,2) NOT NULL CHECK (monto > 0.00),
    url_voucher TEXT NOT NULL,
    idempotency_hash VARCHAR(64) NOT NULL UNIQUE,
    estado VARCHAR(20) NOT NULL DEFAULT 'EN_REVISION' CHECK (estado IN ('EN_REVISION', 'APROBADO', 'RECHAZADO', 'OBSERVADO')),
    motivo_rechazo TEXT,
    conciliado_por UUID,
    conciliado_en TIMESTAMP WITH TIME ZONE,
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- 6. Tabla de Áreas Comunes
CREATE TABLE areas_comunes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE CASCADE,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    aforo_maximo INT NOT NULL CHECK (aforo_maximo > 0),
    costo_reserva NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (costo_reserva >= 0.00),
    esta_activa BOOLEAN NOT NULL DEFAULT TRUE
);

-- 7. Tabla de Reservas (Brandon - PROC-04)
CREATE TABLE reservas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    area_id UUID NOT NULL REFERENCES areas_comunes(id) ON DELETE RESTRICT,
    departamento_id UUID NOT NULL REFERENCES departamentos(id) ON DELETE RESTRICT,
    fecha_reserva DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL CHECK (hora_fin > hora_inicio),
    costo_reserva NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (costo_reserva >= 0.00),
    estado VARCHAR(20) NOT NULL DEFAULT 'SOLICITADA' CHECK (estado IN ('SOLICITADA', 'CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'COMPLETADA')),
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL
);

-- 8. Bitácora Inmutable de Auditoría (7 campos obligatorios)
CREATE TABLE auditoria_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    departamento_id UUID,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    accion_ejecutada VARCHAR(100) NOT NULL,
    motivo TEXT NOT NULL,
    resultado VARCHAR(20) NOT NULL CHECK (resultado IN ('EXITOSO', 'FALLIDO')),
    actor_tipo VARCHAR(30) NOT NULL,
    actor_id VARCHAR(100) NOT NULL,
    estado_anterior JSONB NOT NULL DEFAULT '{}'::jsonb,
    estado_posterior JSONB NOT NULL DEFAULT '{}'::jsonb,
    hash_actual VARCHAR(64) NOT NULL,
    hash_previo VARCHAR(64)
);

-- Índices de Rendimiento y Concurrencia
CREATE INDEX idx_presupuestos_condominio_estado
    ON presupuestos_mensuales(condominio_id, estado);
CREATE INDEX idx_cuotas_depto_estado ON cuotas_mantenimiento(departamento_id, estado);
CREATE INDEX idx_comprobantes_hash ON comprobantes_pago(idempotency_hash);
CREATE INDEX idx_reservas_bloqueo ON reservas(area_id, fecha_reserva, hora_inicio, hora_fin) WHERE estado = 'CONFIRMADA';
CREATE INDEX idx_auditoria_depto_fecha ON auditoria_logs(departamento_id, timestamp DESC);
