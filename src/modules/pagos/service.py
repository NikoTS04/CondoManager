"""Servicio del Dominio de Pagos y Conciliación (Tarqui - PROC-02).

Implementa:
1. Hash de idempotencia SHA-256 para evitar duplicidad de comprobantes.
2. Conciliación y algoritmo de imputación contable en orden de prelación.
3. Restablecimiento de solvencia financiera para reservas de áreas comunes.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
from typing import Dict, List, Optional
import uuid

from src.core.audit import AuditoriaPayload
from src.modules.pagos.schemas import (
    ComprobanteRecibidoResponse,
    ConciliacionResultResponse,
    ReportarPagoRequest,
)
from src.shared.decimal_types import redondear_moneda


class VoucherDuplicadoException(Exception):
    def __init__(self, error_code: str, mensaje: str):
        super().__init__(mensaje)
        self.error_code = error_code
        self.mensaje = mensaje


class PagosService:
    @staticmethod
    def calcular_hash_idempotencia(
        condominio_id: str,
        banco: str,
        numero_operacion: str,
        fecha_operacion: date,
        monto: Decimal,
    ) -> str:
        """Calcula el hash SHA-256 normalizado según specs/01-architecture/idempotency-and-deduplication.md."""
        banco_norm = banco.strip().upper()
        num_op_clean = numero_operacion.strip().lstrip("0") or "0"
        fecha_str = fecha_operacion.isoformat()
        monto_str = f"{redondear_moneda(monto):.2f}"

        cadena = f"{condominio_id}|{banco_norm}|{num_op_clean}|{fecha_str}|{monto_str}"
        return hashlib.sha256(cadena.encode("utf-8")).hexdigest()

    @classmethod
    def procesar_reporte_pago(
        cls,
        request: ReportarPagoRequest,
        condominio_id: str,
        comprobantes_existentes: Dict[str, Dict],
    ) -> ComprobanteRecibidoResponse:
        """Valida y registra un nuevo comprobante bancario garantizando idempotencia."""
        idempotency_hash = cls.calcular_hash_idempotencia(
            condominio_id=condominio_id,
            banco=request.banco,
            numero_operacion=request.numero_operacion,
            fecha_operacion=request.fecha_operacion,
            monto=request.monto,
        )

        if idempotency_hash in comprobantes_existentes:
            previo = comprobantes_existentes[idempotency_hash]
            if previo["estado"] == "APROBADO":
                raise VoucherDuplicadoException(
                    error_code="VOUCHER_YA_CONCILIADO",
                    mensaje="El voucher bancario ya fue conciliado y aplicado anteriormente.",
                )
            # Si está EN_REVISION, retornamos el comprobante previo sin duplicar
            return ComprobanteRecibidoResponse(
                comprobante_id=previo["id"],
                estado=previo["estado"],
                mensaje="El comprobante ya fue recibido previamente y se encuentra en revisión.",
                idempotency_hash=idempotency_hash,
            )

        nuevo_id = uuid.uuid4()
        comprobante_data = {
            "id": nuevo_id,
            "departamento_id": request.departamento_id,
            "banco_origen": request.banco,
            "numero_operacion": request.numero_operacion,
            "fecha_operacion": request.fecha_operacion,
            "monto": redondear_moneda(request.monto),
            "url_voucher": request.url_voucher,
            "idempotency_hash": idempotency_hash,
            "estado": "EN_REVISION",
            "creado_en": datetime.now(timezone.utc),
        }
        comprobantes_existentes[idempotency_hash] = comprobante_data

        return ComprobanteRecibidoResponse(
            comprobante_id=nuevo_id,
            estado="EN_REVISION",
            mensaje="Comprobante recibido. En proceso de conciliación por la Junta Directiva.",
            idempotency_hash=idempotency_hash,
        )

    @classmethod
    def conciliar_comprobante(
        cls,
        comprobante: Dict,
        decision: str,
        cuotas_pendientes: List[Dict],
        departamento: Dict,
        motivo_rechazo: Optional[str] = None,
    ) -> ConciliacionResultResponse:
        """Aplica la decisión de la junta e imputa fondos en riguroso orden de prelación."""
        if decision == "RECHAZADO":
            if not motivo_rechazo or not motivo_rechazo.strip():
                raise ValueError("El rechazo de un comprobante requiere especificar un motivo obligatorio.")
            comprobante["estado"] = "RECHAZADO"
            comprobante["motivo_rechazo"] = motivo_rechazo

            return ConciliacionResultResponse(
                comprobante_id=comprobante["id"],
                estado_final="RECHAZADO",
                monto_imputado=Decimal("0.00"),
                nuevo_saldo_departamento=sum(c["monto_total_exigible"] - c["monto_pagado"] for c in cuotas_pendientes),
                saldo_a_favor_generado=Decimal("0.00"),
                departamento_habilitado_reservas=(departamento.get("estado_financiero") == "AL_DIA"),
            )

        # Decisión == APROBADO: Imputación contable
        comprobante["estado"] = "APROBADO"
        monto_disponible = redondear_moneda(comprobante["monto"])
        total_imputado = Decimal("0.00")

        # Orden de prelación: Cuotas vencidas más antiguas primero
        cuotas_ordenadas = sorted(cuotas_pendientes, key=lambda c: c["fecha_vencimiento"])

        for cuota in cuotas_ordenadas:
            if monto_disponible <= Decimal("0.00"):
                break

            saldo_pendiente_cuota = cuota["monto_total_exigible"] - cuota["monto_pagado"]
            if saldo_pendiente_cuota <= Decimal("0.00"):
                continue

            if monto_disponible >= saldo_pendiente_cuota:
                # Liquidación total de la cuota
                monto_a_aplicar = saldo_pendiente_cuota
                cuota["monto_pagado"] += monto_a_aplicar
                cuota["estado"] = "PAGADA"
                monto_disponible -= monto_a_aplicar
                total_imputado += monto_a_aplicar
            else:
                # Abono parcial
                monto_a_aplicar = monto_disponible
                cuota["monto_pagado"] += monto_a_aplicar
                cuota["estado"] = "PAGO_PARCIAL"
                total_imputado += monto_a_aplicar
                monto_disponible = Decimal("0.00")

        # Si aún queda dinero tras pagar todas las cuotas pendientes -> Saldo a Favor
        saldo_a_favor_nuevo = Decimal("0.00")
        if monto_disponible > Decimal("0.00"):
            departamento["saldo_a_favor"] = redondear_moneda(departamento.get("saldo_a_favor", Decimal("0.00")) + monto_disponible)
            saldo_a_favor_nuevo = monto_disponible

        # Evaluar si el departamento queda al día
        deudas_restantes = sum(
            c["monto_total_exigible"] - c["monto_pagado"]
            for c in cuotas_pendientes
            if c["estado"] != "PAGADA"
        )

        cuotas_en_mora = any(c["estado"] == "EN_MORA" for c in cuotas_pendientes)
        if not cuotas_en_mora and deudas_restantes == Decimal("0.00"):
            departamento["estado_financiero"] = "AL_DIA"
            habilitado_reservas = True
        else:
            habilitado_reservas = (departamento.get("estado_financiero") == "AL_DIA")

        # Registro inmutable de auditoría (7 campos obligatorios)
        AuditoriaPayload(
            condominio_id="condominio-context",
            departamento_id=str(departamento["id"]),
            accion_ejecutada="CONCILIACION_PAGO_APROBADA",
            motivo=f"Comprobante de {comprobante['banco_origen']} aprobado e imputado a cuotas.",
            resultado="EXITOSO",
            estado_anterior={"deuda": str(deudas_restantes + total_imputado)},
            estado_posterior={
                "monto_imputado": str(total_imputado),
                "deuda_restante": str(deudas_restantes),
                "saldo_a_favor": str(departamento.get("saldo_a_favor", "0.00")),
                "estado_financiero": departamento.get("estado_financiero"),
            },
        )

        return ConciliacionResultResponse(
            comprobante_id=comprobante["id"],
            estado_final="APROBADO",
            monto_imputado=redondear_moneda(total_imputado),
            nuevo_saldo_departamento=redondear_moneda(deudas_restantes),
            saldo_a_favor_generado=redondear_moneda(saldo_a_favor_nuevo),
            departamento_habilitado_reservas=habilitado_reservas,
        )
