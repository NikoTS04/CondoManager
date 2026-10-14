"""Servicio de Negocio del Dominio de Cuotas (Anderson - PROC-01).

Implementa la emisión masiva mensual, cálculo de alícuotas con Decimal y amortización de saldos a favor.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from src.core.audit import AuditoriaPayload
from src.modules.cuotas.saldos.service import aplicar_saldo_a_favor
from src.modules.cuotas.schemas import (
    EmitirLoteCuotasRequest,
    EmitirLoteCuotasResponse,
)
from src.shared.decimal_types import calcular_cuota_alicuota, redondear_moneda


class LoteYaEmitidoException(Exception):
    def __init__(self, periodo: str):
        super().__init__(f"El lote de cuotas para el periodo '{periodo}' ya fue emitido previamente.")
        self.periodo = periodo


class CuotasService:
    @staticmethod
    def calcular_emision_departamento(
        departamento_id: uuid.UUID,
        departamento_numero: str,
        coeficiente: Decimal,
        saldo_a_favor: Decimal,
        presupuesto_total: Decimal,
        periodo: str,
        fecha_emision: date,
        fecha_vencimiento: date,
        *,
        monto_bruto_final: Decimal | None = None,
    ) -> dict:
        """Calcula de forma determinista la cuota de una unidad aplicando amortizaciones según PROC-01."""
        cuota_bruta = (
            calcular_cuota_alicuota(presupuesto_total, coeficiente)
            if monto_bruto_final is None
            else redondear_moneda(monto_bruto_final)
        )
        cuota_id = uuid.uuid4()
        amortizacion = aplicar_saldo_a_favor(cuota_bruta, saldo_a_favor)
        monto_descuento = Decimal("0.00")
        monto_exigible = cuota_bruta
        monto_pagado = amortizacion.monto_aplicado
        estado = amortizacion.estado
        nuevo_saldo_a_favor = amortizacion.saldo_restante
        cubierta_saldo_favor = estado == "PAGADA" and monto_pagado > 0

        # 7 campos obligatorios de auditoría
        audit_log = AuditoriaPayload(
            condominio_id="condominio-context",
            departamento_id=str(departamento_id),
            accion_ejecutada="EMISION_CUOTA_ORDINARIA",
            motivo=f"Emisión mensual automatizada periodo {periodo} con alícuota {coeficiente}%",
            resultado="EXITOSO",
            estado_anterior={
                "saldo_a_favor_previo": str(saldo_a_favor),
                "estado_cuota": "NO_EMITIDA",
            },
            estado_posterior={
                "cuota_id": str(cuota_id),
                "monto_ordinario": str(cuota_bruta),
                "monto_descuento": str(monto_descuento),
                "monto_total_exigible": str(monto_exigible),
                "monto_aplicado": str(monto_pagado),
                "monto_pendiente": str(amortizacion.monto_pendiente),
                "saldo_a_favor_restante": str(nuevo_saldo_a_favor),
                "estado_cuota": estado,
            },
        )

        return {
            "cuota_id": cuota_id,
            "departamento_id": departamento_id,
            "departamento_numero": departamento_numero,
            "periodo": periodo,
            "monto_ordinario": cuota_bruta,
            "monto_extraordinario": Decimal("0.00"),
            "monto_mora": Decimal("0.00"),
            "monto_descuento": monto_descuento,
            "monto_total_exigible": monto_exigible,
            "monto_pagado": monto_pagado,
            "monto_pendiente": amortizacion.monto_pendiente,
            "fecha_emision": fecha_emision,
            "fecha_vencimiento": fecha_vencimiento,
            "estado": estado,
            "nuevo_saldo_a_favor": nuevo_saldo_a_favor,
            "cubierta_saldo_favor": cubierta_saldo_favor,
            "audit_log": audit_log,
        }

    @classmethod
    def emitir_lote_en_memoria(
        cls,
        request: EmitirLoteCuotasRequest,
        departamentos: list[dict],
        lotes_existentes: list[str] | None = None,
    ) -> EmitirLoteCuotasResponse:
        """Orquesta la emisión de un lote para un conjunto de departamentos."""
        lotes_existentes = lotes_existentes or []
        if request.periodo in lotes_existentes:
            raise LoteYaEmitidoException(request.periodo)

        fecha_emision_dt = datetime.now(UTC)
        fecha_emision_date = fecha_emision_dt.date()
        # El crédito se aplica únicamente cuando el bruto ya incluye el ajuste residual.
        brutos = [
            calcular_cuota_alicuota(request.presupuesto_total, depto["coeficiente"])
            for depto in departamentos
        ]
        total_facturado = sum(brutos, Decimal("0.00"))
        diferencia = request.presupuesto_total - total_facturado
        if diferencia != Decimal("0.00") and brutos:
            indice_mayor = max(range(len(brutos)), key=lambda indice: brutos[indice])
            brutos[indice_mayor] = redondear_moneda(brutos[indice_mayor] + diferencia)
            total_facturado += diferencia
        cuotas_cubiertas = 0

        resultados = []
        for depto, bruto in zip(departamentos, brutos, strict=True):
            resultado = cls.calcular_emision_departamento(
                departamento_id=depto.get("id", uuid.uuid4()),
                departamento_numero=depto["numero"],
                coeficiente=depto["coeficiente"],
                saldo_a_favor=depto.get("saldo_a_favor", Decimal("0.00")),
                presupuesto_total=request.presupuesto_total,
                periodo=request.periodo,
                fecha_emision=fecha_emision_date,
                fecha_vencimiento=request.fecha_vencimiento,
                monto_bruto_final=bruto,
            )
            resultados.append(resultado)
            if resultado["cubierta_saldo_favor"]:
                cuotas_cubiertas += 1

        return EmitirLoteCuotasResponse(
            lote_id=uuid.uuid4(),
            periodo=request.periodo,
            total_cuotas_emitidas=len(departamentos),
            monto_total_facturado=redondear_moneda(total_facturado),
            cuotas_cubiertas_saldo_favor=cuotas_cubiertas,
            fecha_emision=fecha_emision_dt,
            fecha_vencimiento=request.fecha_vencimiento,
        )
