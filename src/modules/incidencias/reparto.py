"""Reparto exacto, publicación idempotente y lectura privada de cargos."""

import json
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import or_, select

from src.core.authorization import contexto_consulta, denegar
from src.core.errors import APIError
from src.core.security import validar_sesion
from src.modules.condominios.models import Condominio, Departamento, Edificio
from src.modules.incidencias.models import ActualizacionIncidencia, Incidencia
from src.modules.incidencias.reparto_models import CargoIncidencia, RepartoIncidencia
from src.modules.incidencias.service import contexto_junta
from src.modules.pagos.repository import SQLAlchemyPagosRepository
from src.modules.usuarios.repository import SQLAlchemyUsuariosRepository
from src.shared.decimal_types import Decimal

CERO = Decimal("0.00")
CENTAVO = Decimal("0.01")


class ConfigurarReparto(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alcance: Literal["TODOS", "SELECCIONADOS"]
    metodo: Literal["EQUITATIVA", "POR_ALICUOTA"]
    departamento_ids: list[UUID] = Field(default_factory=list, max_length=10000)
    concepto: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    motivo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]

    @model_validator(mode="after")
    def participantes(self):
        if len(set(self.departamento_ids)) != len(self.departamento_ids):
            raise ValueError("No repita departamentos.")
        if (self.alcance == "SELECCIONADOS") != bool(self.departamento_ids):
            raise ValueError("Seleccione departamentos solo para el alcance SELECCIONADOS.")
        if "\x00" in self.concepto or "\x00" in self.motivo:
            raise ValueError("Texto no válido.")
        return self


class PublicarReparto(ConfigurarReparto):
    huella: str = Field(pattern=r"^[a-f0-9]{64}$")


class ParticipanteReparto(BaseModel):
    departamento_id: UUID
    numero: str
    edificio: str
    coeficiente: str
    monto: str


class RepartoDTO(BaseModel):
    id: UUID | None = None
    incidencia_id: UUID
    actualizacion_id: UUID
    concepto: str
    motivo: str
    alcance: Literal["TODOS", "SELECCIONADOS"]
    metodo: Literal["EQUITATIVA", "POR_ALICUOTA"]
    monto: str
    moneda: Literal["PEN", "USD"]
    huella: str
    participantes: list[ParticipanteReparto]


class CargoDTO(BaseModel):
    id: UUID
    incidencia_id: UUID
    actualizacion_id: UUID
    concepto: str
    moneda: str
    monto: str
    pagado: str
    pendiente: str
    estado: Literal["PENDIENTE", "PAGADO"]


def distribuir(monto: Decimal, pesos: dict[UUID, Decimal]) -> dict[UUID, Decimal]:
    """Mayor residuo en enteros: ni float ni errores de precisión por divisiones."""
    if (
        not monto.is_finite()
        or monto <= CERO
        or monto != monto.quantize(CENTAVO)
        or not pesos
        or any(not p.is_finite() or p <= 0 for p in pesos.values())
    ):
        raise APIError(422, "REPARTO_INVALIDO", "Revise el monto y los coeficientes.")
    escala = max(0, -min(p.as_tuple().exponent for p in pesos.values()))
    enteros = {id: int(p * 10**escala) for id, p in pesos.items()}
    total = sum(enteros.values())
    centavos = int(monto * 100)
    bases = {id: centavos * p // total for id, p in enteros.items()}
    orden = sorted(enteros, key=lambda id: (-(centavos * enteros[id] % total), str(id)))
    for id in orden[: centavos - sum(bases.values())]:
        bases[id] += 1
    return {id: Decimal(n) * CENTAVO for id, n in bases.items()}


def huella(datos):
    return sha256(json.dumps(datos, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


class RepartosService:
    def __init__(self, session):
        self.session = session

    async def _contexto(self, usuario, bloquear=False):
        cid = contexto_junta(usuario)
        identidad = SQLAlchemyUsuariosRepository(self.session)
        if await identidad.contexto(cid, bloquear=bloquear) is None:
            denegar()
        return cid, await validar_sesion(usuario, identidad)

    async def _preview(self, cid, iid, aid, solicitud):
        costo = await self.session.scalar(
            select(ActualizacionIncidencia)
            .join(Incidencia, ActualizacionIncidencia.incidencia_id == Incidencia.id)
            .where(
                Incidencia.condominio_id == cid,
                Incidencia.id == iid,
                ActualizacionIncidencia.id == aid,
            )
        )
        if costo is None or costo.monto is None or costo.monto <= CERO:
            raise APIError(404, "COSTO_NO_REPARTIBLE", "No existe un costo positivo disponible.")
        query = (
            select(Departamento, Edificio.nombre_bloque)
            .join(Edificio, Departamento.edificio_id == Edificio.id)
            .where(Edificio.condominio_id == cid, Departamento.activo.is_(True))
            .order_by(Departamento.id)
        )
        if solicitud.alcance == "SELECCIONADOS":
            query = query.where(Departamento.id.in_(solicitud.departamento_ids))
        filas = (await self.session.execute(query)).all()
        if not filas or (
            solicitud.alcance == "SELECCIONADOS" and len(filas) != len(solicitud.departamento_ids)
        ):
            raise APIError(
                422, "PARTICIPANTES_INVALIDOS", "Seleccione unidades activas del condominio."
            )
        importes = distribuir(
            costo.monto,
            {
                d.id: d.coeficiente_participacion
                if solicitud.metodo == "POR_ALICUOTA"
                else Decimal("1")
                for d, _ in filas
            },
        )
        condominio = await self.session.get(Condominio, cid)
        datos = {
            "incidencia_id": str(iid),
            "actualizacion_id": str(aid),
            "concepto": solicitud.concepto,
            "motivo": solicitud.motivo,
            "alcance": solicitud.alcance,
            "metodo": solicitud.metodo,
            "monto": f"{costo.monto:.2f}",
            "moneda": condominio.moneda,
            "participantes": [
                {
                    "departamento_id": str(d.id),
                    "numero": d.numero,
                    "edificio": edificio,
                    "coeficiente": f"{d.coeficiente_participacion:.4f}",
                    "monto": f"{importes[d.id]:.2f}",
                }
                for d, edificio in filas
            ],
        }
        return {**datos, "huella": huella(datos)}

    async def previsualizar(self, usuario, iid, aid, solicitud):
        async with self.session.begin():
            cid, _ = await self._contexto(usuario)
            return await self._preview(cid, iid, aid, solicitud)

    async def consultar(self, usuario, iid, aid):
        async with self.session.begin():
            cid, _ = await self._contexto(usuario)
            reparto = await self.session.scalar(
                select(RepartoIncidencia).where(
                    RepartoIncidencia.condominio_id == cid,
                    RepartoIncidencia.incidencia_id == iid,
                    RepartoIncidencia.actualizacion_id == aid,
                )
            )
            if reparto is None:
                raise APIError(404, "REPARTO_NO_ENCONTRADO", "El costo aún no tiene un reparto.")
            return {"id": reparto.id, **reparto.instantanea}

    async def publicar(self, usuario, iid, aid, solicitud, clave):
        datos = solicitud.model_dump(mode="json")
        datos["departamento_ids"] = sorted(datos["departamento_ids"])
        hash_request = huella({"iid": str(iid), "aid": str(aid), **datos})
        async with self.session.begin():
            cid, vigente = await self._contexto(usuario, bloquear=True)
            previo = await self.session.scalar(
                select(RepartoIncidencia).where(
                    RepartoIncidencia.condominio_id == cid,
                    or_(
                        RepartoIncidencia.clave_idempotencia == clave,
                        RepartoIncidencia.actualizacion_id == aid,
                    ),
                )
            )
            if previo:
                if previo.clave_idempotencia != clave or previo.hash_solicitud != hash_request:
                    raise APIError(
                        409, "REPARTO_YA_PUBLICADO", "El costo o la clave ya se publicaron."
                    )
                return {"id": previo.id, **previo.instantanea}, False
            preview = await self._preview(cid, iid, aid, solicitud)
            if preview["huella"] != solicitud.huella:
                raise APIError(
                    409, "REPARTO_DESACTUALIZADO", "Previsualice de nuevo antes de confirmar."
                )
            reparto = RepartoIncidencia(
                condominio_id=cid,
                incidencia_id=iid,
                actualizacion_id=aid,
                clave_idempotencia=clave,
                hash_solicitud=hash_request,
                concepto=solicitud.concepto,
                motivo=solicitud.motivo,
                alcance=solicitud.alcance,
                metodo=solicitud.metodo,
                monto=Decimal(preview["monto"]),
                instantanea=preview,
                actor_id=UUID(vigente["sub"]),
            )
            self.session.add(reparto)
            await self.session.flush()
            for p in preview["participantes"]:
                self.session.add(
                    CargoIncidencia(
                        reparto_id=reparto.id,
                        departamento_id=UUID(p["departamento_id"]),
                        monto=Decimal(p["monto"]),
                    )
                )
            await SQLAlchemyPagosRepository(self.session).auditar(
                vigente,
                cid,
                None,
                "PUBLICACION_REPARTO_INCIDENCIA",
                solicitud.motivo,
                {},
                {"reparto_id": str(reparto.id), **preview},
            )
            return {"id": reparto.id, **preview}, True

    async def cargos(self, usuario, did):
        async with self.session.begin():
            depto, condominio = await SQLAlchemyPagosRepository(self.session).departamento(
                did, usuario
            )
            filas = (
                await self.session.execute(
                    select(CargoIncidencia, RepartoIncidencia)
                    .join(RepartoIncidencia, CargoIncidencia.reparto_id == RepartoIncidencia.id)
                    .where(
                        CargoIncidencia.departamento_id == depto.id,
                        RepartoIncidencia.condominio_id
                        == contexto_consulta(usuario, condominio.id),
                    )
                    .order_by(RepartoIncidencia.creado_en, CargoIncidencia.id)
                )
            ).all()
            return [
                {
                    "id": c.id,
                    "incidencia_id": r.incidencia_id,
                    "actualizacion_id": r.actualizacion_id,
                    "concepto": r.concepto,
                    "moneda": condominio.moneda,
                    "monto": f"{c.monto:.2f}",
                    "pagado": f"{c.pagado:.2f}",
                    "pendiente": f"{c.monto - c.pagado:.2f}",
                    "estado": "PAGADO" if c.pagado == c.monto else "PENDIENTE",
                }
                for c, r in filas
            ]
