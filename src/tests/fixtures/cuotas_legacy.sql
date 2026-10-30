-- Extracto del backup anterior a CON-11. Se versiona para probar adopción en CI
-- sin depender del archivo local/ignorado condomanager_schema.sql.
CREATE TABLE IF NOT EXISTS cuotas_mantenimiento (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    departamento_id UUID NOT NULL REFERENCES departamentos(id) ON DELETE RESTRICT,
    periodo VARCHAR(7) NOT NULL,
    monto_ordinario NUMERIC(12,2) NOT NULL,
    monto_extraordinario NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    monto_mora NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    monto_descuento NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    monto_total_exigible NUMERIC(12,2) NOT NULL,
    monto_pagado NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    fecha_emision DATE NOT NULL,
    fecha_vencimiento DATE NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'EMITIDA',
    CONSTRAINT uq_departamento_periodo UNIQUE (departamento_id, periodo),
    CONSTRAINT ck_cuota_monto_ordinario CHECK (monto_ordinario >= 0.00),
    CONSTRAINT ck_cuota_monto_extraordinario CHECK (monto_extraordinario >= 0.00),
    CONSTRAINT ck_cuota_monto_mora CHECK (monto_mora >= 0.00),
    CONSTRAINT ck_cuota_monto_descuento CHECK (monto_descuento >= 0.00),
    CONSTRAINT ck_cuota_monto_total_exigible CHECK (monto_total_exigible >= 0.00),
    CONSTRAINT ck_cuota_monto_pagado CHECK (monto_pagado BETWEEN 0.00 AND monto_total_exigible),
    CONSTRAINT ck_cuota_estado CHECK (
        estado IN ('EMITIDA', 'PENDIENTE', 'PAGO_PARCIAL', 'PAGADA', 'VENCIDA', 'EN_MORA')
    )
);
COMMENT ON TABLE cuotas_mantenimiento IS 'Cuota de mantenimiento mensual por departamento (PROC-01).';
COMMENT ON COLUMN cuotas_mantenimiento.periodo IS 'Período YYYY-MM al que corresponde la cuota.';
COMMENT ON COLUMN cuotas_mantenimiento.monto_total_exigible IS 'Suma de ordinario + extraordinario + mora − descuento.';
COMMENT ON COLUMN cuotas_mantenimiento.estado IS 'EMITIDA | PENDIENTE | PAGO_PARCIAL | PAGADA | VENCIDA | EN_MORA.';
CREATE INDEX IF NOT EXISTS idx_cuotas_departamento ON cuotas_mantenimiento(departamento_id);
CREATE INDEX IF NOT EXISTS idx_cuotas_periodo ON cuotas_mantenimiento(periodo);
CREATE INDEX IF NOT EXISTS idx_cuotas_estado ON cuotas_mantenimiento(estado);
CREATE INDEX IF NOT EXISTS idx_cuotas_depto_estado ON cuotas_mantenimiento(departamento_id, estado);
