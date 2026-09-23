"""Servicio del Motor de Moras Automatizado (Tarqui - PROC-02).

Evalúa vencimientos tras expirar el periodo de gracia y aplica recargos,
respetando la regla de postergación protectora ante comprobantes en revisión.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List
import uuid

from src.core.audit import AuditoriaPayload
from src.modules.pagos.schemas import EvaluarMorasResponse
from src.shared.decimal_types import redondear_moneda


class MotorMorasService:
    @staticmethod
    def evaluar_y_aplicar_moras(
        cuotas: List[Dict],
        departamentos: Dict[uuid.UUID, Dict],
        comprobantes_en_revision_por_depto: Dict[uuid.UUID, bool],
        fecha_evaluacion: date,
        dias_gracia: int = 2,
        monto_mora_fijo: Decimal = Decimal("20.00"),
    ) -> EvaluarMorasResponse:
        """Evalúa un lote de cuotas y aplica recargos punitorios a las que agotaron la gracia sin comprobante."""
        cuotas_evaluadas = len(cuotas)
        moras_aplicadas = 0
        postergadas_por_revision = 0
        monto_total_moras = Decimal("0.00")

        for cuota in cuotas:
            # Solo evaluamos cuotas que no están pagadas
            if cuota["estado"] in ["PAGADA"]:
                continue

            fecha_limite_gracia = cuota["fecha_vencimiento"] + timedelta(days=dias_gracia)
            if fecha_evaluacion > fecha_limite_gracia:
                depto_id = cuota["departamento_id"]

                # Regla de Postergación Protectora: Si el residente subió un voucher que la junta no ha revisado
                if comprobantes_en_revision_por_depto.get(depto_id, False):
                    postergadas_por_revision += 1
                    continue

                # Si no tiene comprobante en revisión y no tenía mora previa
                if cuota["estado"] != "EN_MORA":
                    cuota["monto_mora"] = redondear_moneda(cuota.get("monto_mora", Decimal("0.00")) + monto_mora_fijo)
                    cuota["monto_total_exigible"] = redondear_moneda(cuota["monto_total_exigible"] + monto_mora_fijo)
                    cuota["estado"] = "EN_MORA"

                    # Marcar departamento como EN_MORA (bloquea reservas de áreas comunes)
                    if depto_id in departamentos:
                        departamentos[depto_id]["estado_financiero"] = "EN_MORA"

                    moras_aplicadas += 1
                    monto_total_moras += monto_mora_fijo

                    # Registro de auditoría inmutable de 7 campos
                    AuditoriaPayload(
                        condominio_id="condominio-context",
                        departamento_id=str(depto_id),
                        accion_ejecutada="APLICAR_MORA_CORTE",
                        motivo=f"Vencimiento de cuota {cuota['periodo']} tras expirar {dias_gracia} días de gracia.",
                        resultado="EXITOSO",
                        estado_anterior={"estado_cuota": "VENCIDA"},
                        estado_posterior={
                            "estado_cuota": "EN_MORA",
                            "recargo_mora": str(monto_mora_fijo),
                            "nuevo_total_exigible": str(cuota["monto_total_exigible"]),
                            "estado_departamento": "EN_MORA",
                        },
                    )

        return EvaluarMorasResponse(
            cuotas_evaluadas=cuotas_evaluadas,
            moras_aplicadas=moras_aplicadas,
            cuotas_postergadas_por_revision=postergadas_por_revision,
            monto_total_moras=redondear_moneda(monto_total_moras),
        )
