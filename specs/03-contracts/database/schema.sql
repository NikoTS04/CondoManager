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
-- CON-70: extensiones aditivas. Las migraciones Alembic son la fuente ejecutable.
CREATE TABLE imputaciones_pago (
    id UUID PRIMARY KEY,
    comprobante_id UUID NOT NULL REFERENCES comprobantes_pago(id) ON DELETE RESTRICT,
    cuota_id UUID NOT NULL REFERENCES cuotas_mantenimiento(id) ON DELETE RESTRICT,
    monto_aplicado NUMERIC(12,2) NOT NULL CHECK (monto_aplicado > 0.00),
    fecha_imputacion TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE archivos_voucher (
    nombre TEXT PRIMARY KEY,
    departamento_id UUID NOT NULL REFERENCES departamentos(id) ON DELETE RESTRICT,
    usuario_id UUID NOT NULL,
    content_type VARCHAR(30) NOT NULL CHECK (content_type IN ('image/png', 'image/jpeg', 'application/pdf')),
    size_bytes INTEGER NOT NULL CHECK (size_bytes BETWEEN 1 AND 5242880),
    creado_en TIMESTAMPTZ NOT NULL,
    comprobante_id UUID REFERENCES comprobantes_pago(id) ON DELETE RESTRICT
);
CREATE INDEX idx_voucher_pendientes ON archivos_voucher(comprobante_id, creado_en);

CREATE TABLE revisiones_pago (
    id UUID PRIMARY KEY,
    comprobante_id UUID NOT NULL REFERENCES comprobantes_pago(id) ON DELETE RESTRICT,
    decision VARCHAR(20) NOT NULL CHECK (decision IN ('APROBADO', 'OBSERVADO', 'RECHAZADO')),
    motivo TEXT,
    actor_id UUID NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL,
    resultado JSONB NOT NULL,
    archivo_nombre TEXT REFERENCES archivos_voucher(nombre) ON DELETE RESTRICT,
    notas_internas TEXT
);
CREATE INDEX idx_revision_comprobante_fecha ON revisiones_pago(comprobante_id, creado_en);

CREATE TABLE eventos_pago_outbox (
    id UUID PRIMARY KEY,
    comprobante_id UUID NOT NULL REFERENCES comprobantes_pago(id) ON DELETE RESTRICT,
    payload JSONB NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL,
    publicado_en TIMESTAMPTZ
);
CREATE INDEX idx_evento_pago_pendiente ON eventos_pago_outbox(publicado_en, creado_en);

-- 6. Tabla de Áreas Comunes
CREATE TABLE areas_comunes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE CASCADE,
    edificio_id UUID REFERENCES edificios(id) ON DELETE SET NULL,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    aforo_maximo INT NOT NULL CHECK (aforo_maximo > 0),
    costo_reserva NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (costo_reserva >= 0.00),
    esta_activa BOOLEAN NOT NULL DEFAULT TRUE,
    tiempo_maximo_horas INTEGER NOT NULL DEFAULT 4 CHECK (tiempo_maximo_horas >= 1),
    hora_apertura TIME NOT NULL DEFAULT '00:00',
    hora_cierre TIME NOT NULL DEFAULT '23:59',
    CONSTRAINT ck_area_horario_catalogo CHECK (
        hora_cierre > hora_apertura AND EXTRACT(SECOND FROM hora_apertura) = 0
        AND EXTRACT(SECOND FROM hora_cierre) = 0
    )
);
CREATE INDEX idx_areas_catalogo_contexto ON areas_comunes (condominio_id, esta_activa, nombre);

-- 7. Tabla de Reservas (Brandon - PROC-04)
CREATE TABLE reservas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    area_id UUID NOT NULL REFERENCES areas_comunes(id) ON DELETE RESTRICT,
    departamento_id UUID NOT NULL REFERENCES departamentos(id) ON DELETE RESTRICT,
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    fecha_reserva DATE NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL CHECK (hora_fin > hora_inicio),
    costo_reserva NUMERIC(12,2) NOT NULL DEFAULT 0.00 CHECK (costo_reserva >= 0.00),
    estado VARCHAR(20) NOT NULL DEFAULT 'SOLICITADA' CHECK (estado IN ('SOLICITADA', 'CONFIRMADA', 'RECHAZADA', 'CANCELADA', 'COMPLETADA')),
    creado_en TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL,
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    usuario_id UUID REFERENCES usuarios(id) ON DELETE RESTRICT,
    area_nombre TEXT NOT NULL,
    moneda VARCHAR(3) NOT NULL CHECK (moneda IN ('PEN', 'USD')),
    zona_horaria VARCHAR(40) NOT NULL CHECK (zona_horaria IN ('UTC', 'America/Lima')),
    fecha_cancelacion TIMESTAMPTZ,
    cancelado_por UUID REFERENCES usuarios(id) ON DELETE RESTRICT,
    motivo_cancelacion TEXT
);
CREATE INDEX idx_reservas_contexto_unidad ON reservas(condominio_id, departamento_id);
CREATE INDEX idx_reservas_area_fecha ON reservas(area_id, fecha_reserva, estado);

-- CON-73: bloqueos operativos, outbox y cola de comunicaciones durable.
CREATE TABLE bloqueos_area (
    id UUID PRIMARY KEY,
    area_id UUID NOT NULL REFERENCES areas_comunes(id) ON DELETE RESTRICT,
    inicio TIMESTAMPTZ NOT NULL,
    fin TIMESTAMPTZ NOT NULL CHECK (fin > inicio),
    activo BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX ix_bloqueos_area_area_id ON bloqueos_area(area_id);
CREATE TABLE eventos_reserva_outbox (
    id UUID PRIMARY KEY,
    reserva_id UUID NOT NULL REFERENCES reservas(id) ON DELETE RESTRICT,
    payload JSONB NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL,
    publicado_en TIMESTAMPTZ
);
CREATE INDEX ix_eventos_reserva_outbox_reserva_id ON eventos_reserva_outbox(reserva_id);
CREATE INDEX idx_evento_reserva_pendiente ON eventos_reserva_outbox(publicado_en, creado_en);
CREATE TABLE notificaciones_logs (
    id UUID PRIMARY KEY,
    condominio_id UUID NOT NULL REFERENCES condominios(id) ON DELETE RESTRICT,
    departamento_id UUID NOT NULL REFERENCES departamentos(id) ON DELETE RESTRICT,
    usuario_destinatario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    evento_id UUID NOT NULL,
    operacion_id UUID NOT NULL,
    tipo_evento TEXT NOT NULL,
    canal VARCHAR(20) NOT NULL CHECK (canal IN ('EMAIL', 'WHATSAPP', 'SMS', 'PUSH')),
    destinatario TEXT NOT NULL,
    asunto TEXT,
    cuerpo TEXT NOT NULL,
    estado VARCHAR(30) NOT NULL CHECK (estado IN ('EN_COLA', 'ENVIADO', 'ENTREGADO', 'REINTENTANDO', 'FALLIDO_PERMANENTE')),
    transporte VARCHAR(20) NOT NULL CHECK (transporte IN ('SIMULADO', 'PROVEEDOR')),
    ciclo INTEGER NOT NULL CHECK (ciclo >= 1),
    intentos INTEGER NOT NULL CHECK (intentos BETWEEN 0 AND 4),
    proximo_reintento TIMESTAMPTZ,
    bloqueado_hasta TIMESTAMPTZ,
    proveedor_message_id TEXT,
    error_mensaje TEXT,
    fecha_creacion TIMESTAMPTZ NOT NULL,
    fecha_actualizacion TIMESTAMPTZ NOT NULL,
    CONSTRAINT uq_notificacion_logica UNIQUE(evento_id, operacion_id, usuario_destinatario_id, canal)
);
CREATE INDEX idx_notificacion_contexto_usuario ON notificaciones_logs(condominio_id, usuario_destinatario_id);
CREATE INDEX idx_notificacion_pendiente ON notificaciones_logs(estado, proximo_reintento);
CREATE TABLE notificaciones_intentos (
    id UUID PRIMARY KEY,
    notificacion_id UUID NOT NULL REFERENCES notificaciones_logs(id) ON DELETE RESTRICT,
    ciclo INTEGER NOT NULL CHECK (ciclo >= 1),
    numero INTEGER NOT NULL CHECK (numero BETWEEN 1 AND 4),
    iniciado_en TIMESTAMPTZ NOT NULL,
    terminado_en TIMESTAMPTZ,
    error TEXT,
    proveedor_message_id TEXT,
    CONSTRAINT uq_notificacion_intento UNIQUE(notificacion_id, ciclo, numero)
);
CREATE TABLE notificaciones_eventos (
    consumidor TEXT NOT NULL,
    event_id UUID NOT NULL,
    procesado_en TIMESTAMPTZ NOT NULL,
    PRIMARY KEY(consumidor, event_id)
);
CREATE TABLE notificaciones_incidencias (
    clave TEXT PRIMARY KEY,
    motivo TEXT NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL
);
ALTER TABLE reservas ENABLE ROW LEVEL SECURITY;
ALTER TABLE bloqueos_area ENABLE ROW LEVEL SECURITY;
ALTER TABLE eventos_reserva_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE notificaciones_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE notificaciones_intentos ENABLE ROW LEVEL SECURITY;
ALTER TABLE notificaciones_eventos ENABLE ROW LEVEL SECURITY;
ALTER TABLE notificaciones_incidencias ENABLE ROW LEVEL SECURITY;

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
