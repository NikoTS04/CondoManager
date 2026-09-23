"""Servicio de Negocio del Dominio de Cuotas (Anderson - PROC-01).

Implementa la emisión masiva mensual, cálculo de alícuotas con Decimal y amortización de saldos a favor.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Dict, List, Optional
import uuid

from src.core.audit import AuditoriaPayload
from src.modules.cuotas.schemas import (
    CuotaDetalleDTO,
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
    ) -> Dict:
        """Calcula de forma determinista la cuota de una unidad aplicando amortizaciones según PROC-01."""
        cuota_bruta = calcular_cuota_alicuota(presupuesto_total, coeficiente)
        cuota_id = uuid.uuid4()

        if saldo_a_favor >= cuota_bruta:
            # Caso 1: Saldo a favor cubre el 100% de la cuota
            monto_descuento = cuota_bruta
            monto_exigible = Decimal("0.00")
            monto_pagado = cuota_bruta
            estado = "PAGADA"
            nuevo_saldo_a_favor = redondear_moneda(saldo_a_favor - cuota_bruta)
            cubierta_saldo_favor = True
        elif saldo_a_favor > Decimal("0.00"):
            # Caso 2: Saldo a favor cubre parcialmente la cuota
            monto_descuento = saldo_a_favor
            monto_exigible = redondear_moneda(cuota_bruta - saldo_a_favor)
            monto_pagado = saldo_a_favor
            estado = "PENDIENTE"
            nuevo_saldo_a_favor = Decimal("0.00")
            cubierta_saldo_favor = False
        else:
            # Caso 3: Sin saldo a favor previo
            monto_descuento = Decimal("0.00")
            monto_exigible = cuota_bruta
            monto_pagado = Decimal("0.00")
            estado = "PENDIENTE"
            nuevo_saldo_a_favor = Decimal("0.00")
            cubierta_saldo_favor = False

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
        departamentos: List[Dict],
        lotes_existentes: Optional[List[str]] = None,
    ) -> EmitirLoteCuotasResponse:
        """Orquesta la emisión de un lote para un conjunto de departamentos."""
        lotes_existentes = lotes_existentes or []
        if request.periodo in lotes_existentes:
            raise LoteYaEmitidoException(request.periodo)

        fecha_emision_dt = datetime.now(timezone.utc)
        fecha_emision_date = fecha_emision_dt.date()
        total_facturado = Decimal("0.00")
        cuotas_cubiertas = 0

        resultados = []
        for depto in departamentos:
            resultado = cls.calcular_emision_departamento(
                departamento_id=depto.get("id", uuid.uuid4()),
                departamento_numero=depto["numero"],
                coeficiente=depto["coeficiente"],
                saldo_a_favor=depto.get("saldo_a_favor", Decimal("0.00")),
                presupuesto_total=request.presupuesto_total,
                periodo=request.periodo,
                fecha_emision=fecha_emision_date,
                fecha_vencimiento=request.fecha_vencimiento,
            )
            resultados.append(resultado)
            total_facturado += resultado["monto_ordinario"]
            if resultado["cubierta_saldo_favor"]:
                cuotas_cubiertas += 1

        # Invariante de Cierre (PROC-01): Ajuste de centavos residuales si sumatoria difiere por redondeo
        diferencia = request.presupuesto_total - total_facturado
        if diferencia != Decimal("0.00") and resultados:
            depto_mayor = max(resultados, key=lambda r: r["monto_ordinario"])
            depto_mayor["monto_ordinario"] = redondear_moneda(depto_mayor["monto_ordinario"] + diferencia)
            depto_mayor["monto_total_exigible"] = redondear_moneda(depto_mayor["monto_total_exigible"] + diferencia)
            total_facturado += diferencia

        return EmitirLoteCuotasResponse(
            lote_id=uuid.uuid4(),
            periodo=request.periodo,
            total_cuotas_emitidas=len(departamentos),
            monto_total_facturado=redondear_moneda(total_facturado),
            cuotas_cubiertas_saldo_favor=cuotas_cubiertas,
            fecha_emision=fecha_emision_dt,
            fecha_vencimiento=request.fecha_vencimiento,
        )

