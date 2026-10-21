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

-- Configuración vigente de distribución (CON-10)
CREATE TABLE configuraciones_distribucion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    metodo VARCHAR(20) NOT NULL,
    actualizado_por VARCHAR(100) NOT NULL,
    actualizado_en TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT uq_distribucion_condominio UNIQUE (condominio_id),
    CONSTRAINT ck_distribucion_metodo CHECK (metodo IN ('POR_ALICUOTA', 'EQUITATIVA'))
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

-- Identidad y acceso persistentes (CON-04). La concesión global es independiente
-- de las asignaciones por condominio y no es editable mediante las API de alta.
CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    nombre VARCHAR(80) NOT NULL,
    apellido VARCHAR(80) NOT NULL,
    telefono VARCHAR(20),
    documento_identidad VARCHAR(20) NOT NULL,
    esta_activo BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    auth_revision INTEGER NOT NULL DEFAULT 1 CONSTRAINT ck_usuario_auth_revision CHECK (auth_revision >= 1),
    es_superadmin BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE UNIQUE INDEX uq_usuario_email_normalizado ON usuarios (lower(btrim(email)));
CREATE UNIQUE INDEX uq_usuario_documento_normalizado ON usuarios (upper(btrim(documento_identidad)));
CREATE TABLE usuario_roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE CASCADE,
    rol VARCHAR(30) NOT NULL DEFAULT 'RESIDENTE',
    es_activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_usuario_condo_rol UNIQUE (usuario_id, condominio_id),
    CONSTRAINT ck_rol_nombre CHECK (rol IN ('SUPERADMIN', 'ADMIN_JUNTA', 'AUDITOR', 'RESIDENTE'))
);
CREATE TABLE usuario_departamentos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    departamento_id UUID NOT NULL REFERENCES departamentos(id) ON DELETE CASCADE,
    tipo_relacion VARCHAR(30) NOT NULL DEFAULT 'PROPIETARIO_TITULAR',
    es_activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_usuario_depto UNIQUE (usuario_id, departamento_id),
    CONSTRAINT ck_tipo_relacion CHECK (tipo_relacion IN ('PROPIETARIO_TITULAR', 'COPROPIETARIO', 'INQUILINO'))
);

CREATE INDEX idx_vinculos_titulares_activos
    ON usuario_departamentos (departamento_id, tipo_relacion) WHERE es_activo IS TRUE;

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
-- CON-13: evidencia única incluso para aplicación cero; el crédito es un pago.
-- La revisión 0006 (CON-11) completa la FK diferida por 0004.
CREATE TABLE aplicaciones_saldo_favor (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cuota_id UUID NOT NULL CONSTRAINT fk_aplicacion_saldo_cuota
        REFERENCES cuotas_mantenimiento(id) ON DELETE RESTRICT,
    saldo_previo NUMERIC(12,2) NOT NULL,
    monto_aplicado NUMERIC(12,2) NOT NULL,
    monto_pendiente NUMERIC(12,2) NOT NULL,
    saldo_restante NUMERIC(12,2) NOT NULL,
    estado_anterior VARCHAR(20) NOT NULL,
    estado_posterior VARCHAR(20) NOT NULL,
    creado_en TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_aplicacion_saldo_cuota UNIQUE (cuota_id),
    CONSTRAINT ck_aplicacion_saldo_importes CHECK (
        saldo_previo >= 0 AND monto_aplicado >= 0 AND monto_pendiente >= 0
        AND saldo_restante >= 0 AND saldo_previo = monto_aplicado + saldo_restante
    ),
    CONSTRAINT ck_aplicacion_saldo_estados CHECK (
        estado_anterior = 'EMITIDA' AND
        ((estado_posterior = 'PAGADA' AND monto_pendiente = 0) OR
         (estado_posterior = 'PENDIENTE' AND monto_pendiente > 0))
    )
);

-- Resumen histórico e idempotencia del lote (CON-11).
CREATE TABLE lotes_cuotas (
    id UUID PRIMARY KEY,
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    presupuesto_id UUID NOT NULL REFERENCES presupuestos_mensuales(id) ON DELETE RESTRICT,
    periodo VARCHAR(7) NOT NULL,
    metodo VARCHAR(20) NOT NULL CHECK (metodo IN ('POR_ALICUOTA', 'EQUITATIVA')),
    actor_id VARCHAR(150) NOT NULL,
    total_cuotas_emitidas INTEGER NOT NULL CHECK (total_cuotas_emitidas > 0),
    monto_total_facturado NUMERIC(12,2) NOT NULL CHECK (monto_total_facturado > 0),
    cuotas_cubiertas_saldo_favor INTEGER NOT NULL,
    fecha_emision TIMESTAMPTZ NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    CONSTRAINT uq_lote_condominio_periodo UNIQUE (condominio_id, periodo)
);

CREATE TABLE eventos_lote_outbox (
    id UUID PRIMARY KEY,
    lote_id UUID NOT NULL UNIQUE REFERENCES lotes_cuotas(id) ON DELETE RESTRICT,
    payload JSONB NOT NULL,
    publicado_en TIMESTAMPTZ
);

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

-- 9. Tablas Persistentes de Notificaciones, Intentos, Consumo Idempotente y Alertas (CON-32/34/36/37/73 - Migración 20261020_0010)
CREATE TABLE notificaciones (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    departamento_id UUID REFERENCES departamentos(id) ON DELETE RESTRICT,
    usuario_id UUID REFERENCES usuarios(id) ON DELETE RESTRICT,
    evento_id UUID NOT NULL,
    tipo_evento VARCHAR(60) NOT NULL,
    plantilla VARCHAR(50) NOT NULL,
    origen_tipo VARCHAR(20) NOT NULL,
    origen_id UUID NOT NULL,
    clave_deduplicacion VARCHAR(255) NOT NULL,
    canal VARCHAR(10) NOT NULL DEFAULT 'EMAIL',
    destinatario VARCHAR(150) NOT NULL,
    asunto VARCHAR(200),
    cuerpo TEXT NOT NULL,
    contexto JSONB NOT NULL DEFAULT '{}'::jsonb,
    estado VARCHAR(20) NOT NULL DEFAULT 'EN_COLA',
    intentos INTEGER NOT NULL DEFAULT 0,
    ciclo INTEGER NOT NULL DEFAULT 1,
    proximo_intento_en TIMESTAMPTZ,
    bloqueado_hasta TIMESTAMPTZ,
    bloqueado_por VARCHAR(80),
    transporte VARCHAR(40),
    transporte_simulado BOOLEAN,
    proveedor_message_id VARCHAR(150),
    error_codigo VARCHAR(40),
    error_mensaje TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    aceptado_en TIMESTAMPTZ,
    entregado_en TIMESTAMPTZ,
    CONSTRAINT uq_notificacion_entrega_logica UNIQUE (clave_deduplicacion),
    CONSTRAINT ck_notificacion_estado CHECK (
        estado IN ('EN_COLA', 'REINTENTANDO', 'ACEPTADO', 'ENTREGADO', 'FALLIDO_PERMANENTE')
    ),
    CONSTRAINT ck_notificacion_canal CHECK (canal IN ('EMAIL', 'WHATSAPP', 'SMS', 'PUSH')),
    CONSTRAINT ck_notificacion_origen CHECK (
        origen_tipo IN ('CUOTA', 'COMPROBANTE', 'RESERVA', 'COMUNICADO', 'USUARIO')
    ),
    CONSTRAINT ck_notificacion_intentos CHECK (intentos BETWEEN 0 AND 4),
    CONSTRAINT ck_notificacion_ciclo CHECK (ciclo >= 1)
);

CREATE INDEX idx_notificaciones_pendientes
    ON notificaciones (proximo_intento_en)
    WHERE estado IN ('EN_COLA', 'REINTENTANDO');
CREATE INDEX idx_notificaciones_condominio ON notificaciones (condominio_id, creado_en);
CREATE INDEX idx_notificaciones_departamento ON notificaciones (departamento_id, creado_en);
CREATE INDEX idx_notificaciones_origen ON notificaciones (origen_tipo, origen_id);

CREATE TABLE notificacion_intentos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    notificacion_id UUID NOT NULL REFERENCES notificaciones(id) ON DELETE CASCADE,
    ciclo INTEGER NOT NULL DEFAULT 1,
    numero INTEGER NOT NULL,
    worker_id VARCHAR(80) NOT NULL,
    transporte VARCHAR(40) NOT NULL,
    transporte_simulado BOOLEAN NOT NULL,
    resultado VARCHAR(20) NOT NULL,
    codigo VARCHAR(40),
    detalle TEXT,
    proveedor_message_id VARCHAR(150),
    iniciado_en TIMESTAMPTZ NOT NULL,
    finalizado_en TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_intento_numero UNIQUE (notificacion_id, ciclo, numero),
    CONSTRAINT ck_intento_numero CHECK (numero BETWEEN 1 AND 4),
    CONSTRAINT ck_intento_resultado CHECK (
        resultado IN ('ACEPTADO', 'FALLO_TEMPORAL', 'FALLO_DEFINITIVO')
    )
);

CREATE TABLE eventos_consumidos (
    consumidor VARCHAR(60) NOT NULL,
    event_id UUID NOT NULL,
    event_type VARCHAR(60) NOT NULL,
    notificaciones_creadas INTEGER NOT NULL DEFAULT 0,
    procesado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pk_eventos_consumidos PRIMARY KEY (consumidor, event_id)
);

CREATE TABLE alertas_administrativas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    notificacion_id UUID NOT NULL REFERENCES notificaciones(id) ON DELETE CASCADE,
    tipo VARCHAR(40) NOT NULL DEFAULT 'NOTIFICACION_FALLIDA',
    severidad VARCHAR(10) NOT NULL DEFAULT 'BAJA',
    mensaje TEXT NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atendida_en TIMESTAMPTZ,
    atendida_por UUID,
    CONSTRAINT uq_alerta_notificacion_tipo UNIQUE (notificacion_id, tipo),
    CONSTRAINT ck_alerta_severidad CHECK (severidad IN ('BAJA', 'MEDIA', 'ALTA'))
);

CREATE INDEX idx_alertas_abiertas
    ON alertas_administrativas (condominio_id, creado_en)
    WHERE atendida_en IS NULL;
