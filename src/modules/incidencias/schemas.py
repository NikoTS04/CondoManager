from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID

from fastapi import UploadFile
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    condecimal,
    field_validator,
    model_validator,
)


class Urgencia(StrEnum):
    BAJA = "BAJA"
    MEDIA = "MEDIA"
    ALTA = "ALTA"
    URGENTE = "URGENTE"


Categoria = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80, pattern=r"^[^\x00]+$"),
]


class CrearIncidencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    departamento_id: UUID
    ubicacion: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=160)
    ]
    categoria: Categoria
    descripcion: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    urgencia: Urgencia
    evidencia: UploadFile | None = None


class ReporteIncidenciaDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    departamento_id: UUID
    ubicacion: str
    categoria: str
    descripcion: str
    urgencia: Urgencia
    creado_en: datetime
    tiene_evidencia: bool


class RegistroIncidenciaDTO(ReporteIncidenciaDTO):
    estado: Literal["REGISTRADO"] = "REGISTRADO"
    advertencia_evidencia: str | None = None


class IncidenciaDTO(ReporteIncidenciaDTO):
    estado: Literal["REGISTRADO", "RECHAZADO", "ASIGNADO", "EN_PROCESO", "RESUELTO", "CERRADO"]
    categoria_confirmada: str | None
    prioridad: Urgencia | None
    motivo_rechazo: str | None
    version: int
    asignacion_actual_id: UUID | None = None
    responsable_usuario_id: UUID | None = None
    responsable_proveedor_id: UUID | None = None
    fecha_asignacion: datetime | None = None
    plazo: datetime | None = None
    calificacion: int | None = None
    motivo_reapertura: str | None = None
    fecha_cierre: datetime | None = None
    cerrado_por: UUID | None = None


class BandejaIncidenciasDTO(BaseModel):
    items: list[IncidenciaDTO]
    hay_mas: bool


class RevisionIncidencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Annotated[int, Field(ge=1, strict=True)]


class ClasificarIncidencia(RevisionIncidencia):
    accion: Literal["CLASIFICAR"]
    categoria: Categoria
    prioridad: Urgencia


class RechazarIncidencia(RevisionIncidencia):
    accion: Literal["RECHAZAR"]
    motivo: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True, min_length=1, max_length=1000, pattern=r"^[^\x00]+$"
        ),
    ]


RevisarIncidencia = Annotated[
    ClasificarIncidencia | RechazarIncidencia, Field(discriminator="accion")
]


class AsignarIncidencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Annotated[int, Field(ge=1, strict=True)]
    responsable_usuario_id: UUID | None = None
    responsable_proveedor_id: UUID | None = None
    proveedor_nombre: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
        | None
    ) = None
    correo_proveedor: (
        Annotated[str, StringConstraints(strip_whitespace=True, max_length=320)] | None
    ) = None
    plazo: datetime
    nota: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None

    @model_validator(mode="after")
    def responsable_unico(self):
        interno = self.responsable_usuario_id is not None
        proveedor = self.responsable_proveedor_id is not None
        if interno == proveedor:
            raise ValueError("Indica exactamente un responsable: interno o proveedor.")
        if proveedor and not self.proveedor_nombre:
            raise ValueError("El proveedor requiere un nombre.")
        if proveedor and self.proveedor_nombre and "\x00" in self.proveedor_nombre:
            raise ValueError("El nombre del proveedor no es válido.")
        if self.correo_proveedor and (
            "@" not in self.correo_proveedor or "\x00" in self.correo_proveedor
        ):
            raise ValueError("El contacto del proveedor no es válido.")
        if self.plazo.tzinfo is None:
            raise ValueError("El plazo debe incluir zona horaria.")
        return self


class AsignacionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    asignacion_id: UUID
    incidencia_id: UUID
    responsable_usuario_id: UUID | None
    responsable_proveedor_id: UUID | None
    plazo: datetime
    nota: str | None
    estado: Literal["ASIGNADO"] = "ASIGNADO"
    version: int
    avisos_encolados: int = 0


class AvisoAsignacionDTO(BaseModel):
    asignacion_id: UUID
    destinatario_tipo: Literal["RESIDENTE", "PROVEEDOR"]
    estado: Literal[
        "EN_COLA",
        "ENVIADO",
        "ENTREGADO",
        "REINTENTANDO",
        "FALLIDO_PERMANENTE",
        "OMITIDO",
        "CONTACTO_FALTANTE",
    ]
    aviso_id: UUID | None = None
    intentos: int | None = None
    fecha_actualizacion: datetime | None = None
    alerta_abierta: bool = False


class BandejaAvisosDTO(BaseModel):
    items: list[AvisoAsignacionDTO]
    hay_mas: bool


MontoIncidencia = Annotated[
    condecimal(ge=Decimal("0.00"), max_digits=12, decimal_places=2),
    Field(description="Importe decimal de repuestos o servicios; nunca float."),
]


def rechazar_float(valor):
    if isinstance(valor, (float, bool)):
        raise ValueError("El importe debe ser Decimal o cadena; nunca float.")
    return valor


class RegistrarSeguimiento(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Annotated[int, Field(ge=1, strict=True)]
    comentario: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    publico: bool = True
    repuesto: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    monto: MontoIncidencia | None = None

    _validar_monto = field_validator("monto", mode="before")(rechazar_float)


class RegistrarResolucion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Annotated[int, Field(ge=1, strict=True)]
    descripcion: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    publico: bool = True
    repuesto: Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)] | None = None
    monto: MontoIncidencia | None = None

    _validar_monto = field_validator("monto", mode="before")(rechazar_float)


MotivoCierre = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)
]


class ConfirmarIncidencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Annotated[int, Field(ge=1, strict=True)]
    calificacion: Annotated[int, Field(ge=1, le=5, strict=True)]
    comentario: Annotated[str, StringConstraints(strip_whitespace=True, max_length=1000)] | None = (
        None
    )


class ReabrirIncidencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Annotated[int, Field(ge=1, strict=True)]
    motivo: MotivoCierre


class CerrarAdministrativamente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Annotated[int, Field(ge=1, strict=True)]
    motivo: MotivoCierre


class ActualizacionDTO(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    incidencia_id: UUID
    actor_id: UUID
    tipo: Literal["COMENTARIO", "CAMBIO_ESTADO", "COSTO"]
    descripcion: str
    publico: bool
    repuesto: str | None
    monto: Decimal | None
    estado_anterior: str | None
    estado_nuevo: str | None
    tiene_evidencia: bool
    creado_en: datetime


class HistorialIncidenciasDTO(BaseModel):
    items: list[ActualizacionDTO]
    hay_mas: bool
