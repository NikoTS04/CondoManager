"""Servicio de Negocio del Dominio de Condominios y Departamentos.

Da de alta el condominio con su configuración de mora validando la coherencia entre la regla
seleccionada y los parámetros asociados, aplicando precisión decimal estricta (ADR-002).
"""

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.audit import AuditoriaPayload
from src.modules.condominios.models import Condominio, Departamento
from src.modules.condominios.schemas import (
    CondominioDTO,
    CrearCondominioRequest,
    CrearDepartamentoRequest,
    DepartamentoDTO,
    ReglaMoraEnum,
)
from src.shared.decimal_types import redondear_moneda


class ConfiguracionMoraInvalidaException(Exception):
    def __init__(self, mensaje: str):
        super().__init__(mensaje)
        self.mensaje = mensaje


class CondominioNoEncontradoException(Exception):
    def __init__(self, condominio_id: str):
        mensaje = f"El condominio '{condominio_id}' no existe o no fue encontrado."
        super().__init__(mensaje)
        self.error_code = "CONDOMINIO_NO_ENCONTRADO"
        self.mensaje = mensaje
        self.condominio_id = condominio_id


class DepartamentoDuplicadoException(Exception):
    def __init__(self, numero: str):
        mensaje = f"El departamento '{numero}' ya está registrado en este condominio."
        super().__init__(mensaje)
        self.error_code = "DEPARTAMENTO_DUPLICADO"
        self.mensaje = mensaje
        self.numero = numero


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

    @staticmethod
    async def crear_departamento(
        session: AsyncSession, request: CrearDepartamentoRequest
    ) -> tuple[DepartamentoDTO, AuditoriaPayload]:
        """Da de alta una unidad inmobiliaria validando el condominio y la unicidad del número."""
        condominio_existe = await session.scalar(
            select(Condominio.id).where(Condominio.id == request.condominio_id)
        )
        if condominio_existe is None:
            raise CondominioNoEncontradoException(str(request.condominio_id))

        numero_normalizado = request.numero.strip()
        departamento_duplicado = await session.scalar(
            select(Departamento.id).where(
                Departamento.condominio_id == request.condominio_id,
                Departamento.numero == numero_normalizado,
            )
        )
        if departamento_duplicado is not None:
            raise DepartamentoDuplicadoException(numero_normalizado)

        departamento = Departamento(
            condominio_id=request.condominio_id,
            numero=numero_normalizado,
            piso=request.piso,
            coeficiente_participacion=request.coeficiente_participacion,
            saldo_a_favor=redondear_moneda(request.saldo_a_favor),
            estado_financiero=request.estado_financiero.value,
        )
        session.add(departamento)
        await session.flush()

        departamento_dto = DepartamentoDTO.model_validate(departamento)

        audit_alta = AuditoriaPayload(
            condominio_id=str(departamento_dto.condominio_id),
            departamento_id=str(departamento_dto.id),
            accion_ejecutada="ALTA_DEPARTAMENTO",
            motivo=(
                f"Alta del departamento '{departamento_dto.numero}' en piso {departamento_dto.piso} "
                f"con alícuota {departamento_dto.coeficiente_participacion}."
            ),
            resultado="EXITOSO",
            actor_tipo="ADMINISTRADOR",
            estado_anterior={"departamento_id": None},
            estado_posterior={
                "departamento_id": str(departamento_dto.id),
                "numero": departamento_dto.numero,
                "piso": departamento_dto.piso,
                "coeficiente_participacion": str(departamento_dto.coeficiente_participacion),
                "estado_financiero": departamento_dto.estado_financiero.value,
            },
        )

        return departamento_dto, audit_alta
