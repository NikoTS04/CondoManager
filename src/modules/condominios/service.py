"""Servicio de Negocio del Dominio de Condominios y Departamentos.

Da de alta el condominio con su configuración de mora validando la coherencia entre la regla
seleccionada y los parámetros asociados, aplicando precisión decimal estricta (ADR-002).
"""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit import AuditoriaPayload
from src.modules.condominios.models import Condominio
from src.modules.condominios.schemas import (
    CondominioDTO,
    CrearCondominioRequest,
    ReglaMoraEnum,
)
from src.shared.decimal_types import redondear_moneda


class ConfiguracionMoraInvalidaException(Exception):
    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class CondominiosService:
    @staticmethod
    def validar_regla_mora(request: CrearCondominioRequest) -> None:
        """Aplica la regla de negocio: la configuración de mora debe ser coherente con la regla elegida."""
        if request.regla_mora_tipo == ReglaMoraEnum.MONTO_FIJO and (
            request.monto_mora_fijo is None or request.monto_mora_fijo <= Decimal("0.00")
        ):
            raise ConfiguracionMoraInvalidaException(
                "La regla 'MONTO_FIJO' exige un monto de mora fijo mayor a 0.00."
            )
        if (
            request.regla_mora_tipo == ReglaMoraEnum.PORCENTAJE_SALDO
            and request.tasa_mora_porcentaje is None
        ):
            raise ConfiguracionMoraInvalidaException(
                "La regla 'PORCENTAJE_SALDO' exige una tasa de mora porcentual configurada."
            )

    @staticmethod
    async def crear_condominio(
        session: AsyncSession, request: CrearCondominioRequest
    ) -> tuple[CondominioDTO, AuditoriaPayload]:
        """Crea el condominio con su parametrización de mora y registra la auditoría de alta."""
        CondominiosService.validar_regla_mora(request)

        monto_mora_fijo = request.monto_normalizado()

        condominio = Condominio(
            nombre=request.nombre.strip(),
            direccion=request.direccion.strip(),
            moneda=request.moneda.value,
            regla_mora_tipo=request.regla_mora_tipo.value,
            monto_mora_fijo=monto_mora_fijo,
            tasa_mora_porcentaje=request.tasa_mora_porcentaje,
            dias_corte=request.dias_corte,
            dias_gracia=request.dias_gracia,
        )
        session.add(condominio)
        await session.flush()

        condominio_dto = CondominioDTO.model_validate(condominio)

        # Auditoría inmutable con los 7 campos obligatorios (guardarraíl B)
        audit_log = AuditoriaPayload(
            condominio_id=str(condominio_dto.id),
            departamento_id="CONDOMINIO_GENERAL",
            accion_ejecutada="ALTA_CONDOMINIO",
            motivo=(
                f"Alta de condominio con regla de mora '{condominio_dto.regla_mora_tipo.value}', "
                f"corte día {condominio_dto.dias_corte} y {condominio_dto.dias_gracia} días de gracia."
            ),
            resultado="EXITOSO",
            actor_tipo="ADMINISTRADOR",
            actor_id=str(condominio_dto.id),
            estado_anterior={"condominio_id": None},
            estado_posterior={
                "condominio_id": str(condominio_dto.id),
                "nombre": condominio_dto.nombre,
                "moneda": condominio_dto.moneda.value,
                "regla_mora_tipo": condominio_dto.regla_mora_tipo.value,
                "monto_mora_fijo": str(redondear_moneda(condominio_dto.monto_mora_fijo))
                if condominio_dto.monto_mora_fijo is not None
                else None,
                "tasa_mora_porcentaje": str(condominio_dto.tasa_mora_porcentaje)
                if condominio_dto.tasa_mora_porcentaje is not None
                else None,
            },
        )

        return condominio_dto, audit_log
