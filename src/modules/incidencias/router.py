from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Header, Query, Response, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.security import get_current_user
from src.modules.incidencias.reparto import (
    ConfigurarReparto,
    PublicarReparto,
    RepartoDTO,
    RepartosService,
)
from src.modules.incidencias.schemas import (
    AsignacionDTO,
    AsignarIncidencia,
    BandejaAvisosDTO,
    BandejaIncidenciasDTO,
    CerrarAdministrativamente,
    ConfirmarIncidencia,
    CrearIncidencia,
    HistorialIncidenciasDTO,
    IncidenciaDTO,
    ReabrirIncidencia,
    RegistrarResolucion,
    RegistrarSeguimiento,
    RegistroIncidenciaDTO,
    ReporteIncidenciaDTO,
    RevisarIncidencia,
)
from src.modules.incidencias.service import IncidenciasService

router = APIRouter(prefix="/incidencias", tags=["Incidencias"])

Session = Annotated[AsyncSession, Depends(get_db_session)]
SessionReparto = Annotated[AsyncSession, Depends(get_db_session, use_cache=False)]
UsuarioActual = Annotated[dict, Depends(get_current_user)]


@router.post(
    "/{incidencia_id}/costos/{actualizacion_id}/reparto/previsualizacion", response_model=RepartoDTO
)
async def previsualizar_reparto(
    incidencia_id: UUID,
    actualizacion_id: UUID,
    solicitud: ConfigurarReparto,
    response: Response,
    usuario: UsuarioActual,
    session: SessionReparto,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await RepartosService(session).previsualizar(
        usuario,
        incidencia_id,
        actualizacion_id,
        solicitud,
    )


@router.post(
    "/{incidencia_id}/costos/{actualizacion_id}/reparto",
    response_model=RepartoDTO,
    status_code=201,
    responses={200: {"model": RepartoDTO}},
)
async def publicar_reparto(
    incidencia_id: UUID,
    actualizacion_id: UUID,
    solicitud: PublicarReparto,
    clave: Annotated[UUID, Header(alias="Idempotency-Key")],
    response: Response,
    usuario: UsuarioActual,
    session: SessionReparto,
):
    resultado, creado = await RepartosService(session).publicar(
        usuario,
        incidencia_id,
        actualizacion_id,
        solicitud,
        clave,
    )
    response.status_code = 201 if creado else 200
    response.headers["Cache-Control"] = "private, no-store"
    return resultado


@router.get("/{incidencia_id}/costos/{actualizacion_id}/reparto", response_model=RepartoDTO)
async def consultar_reparto(
    incidencia_id: UUID,
    actualizacion_id: UUID,
    response: Response,
    usuario: UsuarioActual,
    session: SessionReparto,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await RepartosService(session).consultar(usuario, incidencia_id, actualizacion_id)


@router.post(
    "",
    status_code=201,
    response_model=RegistroIncidenciaDTO,
    responses={200: {"model": RegistroIncidenciaDTO}},
)
async def registrar_incidencia(
    formulario: Annotated[CrearIncidencia, Form(media_type="multipart/form-data")],
    clave: Annotated[UUID, Header(alias="Idempotency-Key")],
    response: Response,
    usuario: UsuarioActual,
    session: Session,
):
    incidencia, advertencia, creada = await IncidenciasService(session).registrar(
        usuario, formulario, clave
    )
    response.status_code = 201 if creada else 200
    response.headers["Cache-Control"] = "private, no-store"
    return RegistroIncidenciaDTO(
        **ReporteIncidenciaDTO.model_validate(incidencia).model_dump(),
        advertencia_evidencia=advertencia,
    )


@router.get("", response_model=BandejaIncidenciasDTO)
async def listar_incidencias(
    response: Response,
    usuario: UsuarioActual,
    session: Session,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).listar(usuario, offset=offset, limit=limit)


@router.get("/mis-reportes", response_model=BandejaIncidenciasDTO)
async def listar_mis_reportes(
    response: Response,
    usuario: UsuarioActual,
    session: Session,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).listar_propias(usuario, offset=offset, limit=limit)


@router.get("/{incidencia_id}", response_model=IncidenciaDTO)
async def consultar_incidencia(
    incidencia_id: UUID, response: Response, usuario: UsuarioActual, session: Session
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).consultar(usuario, incidencia_id)


@router.patch("/{incidencia_id}/revision", response_model=IncidenciaDTO)
async def revisar_incidencia(
    incidencia_id: UUID,
    revision: RevisarIncidencia,
    response: Response,
    usuario: UsuarioActual,
    session: Session,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).revisar(usuario, incidencia_id, revision)


@router.post(
    "/{incidencia_id}/asignacion",
    status_code=201,
    response_model=AsignacionDTO,
    responses={200: {"model": AsignacionDTO}},
)
async def asignar_incidencia(
    incidencia_id: UUID,
    solicitud: AsignarIncidencia,
    clave: Annotated[UUID, Header(alias="Idempotency-Key")],
    response: Response,
    usuario: UsuarioActual,
    session: Session,
):
    incidencia, asignacion, avisos, creada = await IncidenciasService(session).asignar(
        usuario, incidencia_id, solicitud, clave
    )
    response.status_code = 201 if creada else 200
    response.headers["Cache-Control"] = "private, no-store"
    return AsignacionDTO(
        asignacion_id=asignacion.id,
        incidencia_id=incidencia.id,
        responsable_usuario_id=asignacion.responsable_usuario_id,
        responsable_proveedor_id=asignacion.responsable_proveedor_id,
        plazo=asignacion.plazo,
        nota=asignacion.nota,
        version=incidencia.version,
        avisos_encolados=avisos,
    )


@router.post("/{incidencia_id}/seguimiento", status_code=201, response_model=IncidenciaDTO)
async def registrar_seguimiento(
    incidencia_id: UUID,
    version: Annotated[int, Form(ge=1)],
    comentario: Annotated[str, Form(min_length=1, max_length=2000)],
    response: Response,
    usuario: UsuarioActual,
    session: Session,
    publico: Annotated[bool, Form()] = True,
    repuesto: Annotated[str | None, Form(max_length=120)] = None,
    monto: Annotated[str | None, Form()] = None,
    evidencia: Annotated[UploadFile | None, File()] = None,
):
    incidencia, advertencia = await IncidenciasService(session).registrar_avance(
        usuario,
        incidencia_id,
        RegistrarSeguimiento(
            version=version,
            comentario=comentario,
            publico=publico,
            repuesto=repuesto or None,
            monto=Decimal(monto) if monto and monto.strip() else None,
        ),
        evidencia,
    )
    response.headers["Cache-Control"] = "private, no-store"
    if advertencia:
        response.headers["X-Advertencia-Evidencia"] = advertencia
    return incidencia


@router.post("/{incidencia_id}/resolucion", status_code=201, response_model=IncidenciaDTO)
async def registrar_resolucion(
    incidencia_id: UUID,
    version: Annotated[int, Form(ge=1)],
    descripcion: Annotated[str, Form(min_length=1, max_length=2000)],
    response: Response,
    usuario: UsuarioActual,
    session: Session,
    publico: Annotated[bool, Form()] = True,
    repuesto: Annotated[str | None, Form(max_length=120)] = None,
    monto: Annotated[str | None, Form()] = None,
    evidencia: Annotated[UploadFile | None, File()] = None,
):
    incidencia, advertencia = await IncidenciasService(session).registrar_resolucion(
        usuario,
        incidencia_id,
        RegistrarResolucion(
            version=version,
            descripcion=descripcion,
            publico=publico,
            repuesto=repuesto or None,
            monto=Decimal(monto) if monto and monto.strip() else None,
        ),
        evidencia,
    )
    response.headers["Cache-Control"] = "private, no-store"
    if advertencia:
        response.headers["X-Advertencia-Evidencia"] = advertencia
    return incidencia


@router.post("/{incidencia_id}/confirmacion", response_model=IncidenciaDTO)
async def confirmar_incidencia(
    incidencia_id: UUID,
    solicitud: ConfirmarIncidencia,
    response: Response,
    usuario: UsuarioActual,
    session: Session,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).confirmar(usuario, incidencia_id, solicitud)


@router.post("/{incidencia_id}/reapertura", response_model=IncidenciaDTO)
async def reabrir_incidencia(
    incidencia_id: UUID,
    solicitud: ReabrirIncidencia,
    response: Response,
    usuario: UsuarioActual,
    session: Session,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).reabrir(usuario, incidencia_id, solicitud)


@router.post("/{incidencia_id}/cierre-administrativo", response_model=IncidenciaDTO)
async def cerrar_administrativamente(
    incidencia_id: UUID,
    solicitud: CerrarAdministrativamente,
    response: Response,
    usuario: UsuarioActual,
    session: Session,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).cerrar_administrativamente(
        usuario, incidencia_id, solicitud
    )


@router.get("/{incidencia_id}/historial", response_model=HistorialIncidenciasDTO)
async def consultar_historial(
    incidencia_id: UUID,
    response: Response,
    usuario: UsuarioActual,
    session: Session,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).historial(
        usuario, incidencia_id, offset=offset, limit=limit
    )


@router.get(
    "/{incidencia_id}/actualizaciones/{actualizacion_id}/evidencia",
    response_class=Response,
)
async def consultar_evidencia_actualizacion(
    incidencia_id: UUID, actualizacion_id: UUID, usuario: UsuarioActual, session: Session
):
    actualizacion = await IncidenciasService(session).evidencia_actualizacion(
        usuario, incidencia_id, actualizacion_id
    )
    if not actualizacion.tiene_evidencia:
        raise APIError(404, "EVIDENCIA_NO_ENCONTRADA", "La actualización no tiene evidencia.")
    return Response(
        content=actualizacion.evidencia,
        media_type=actualizacion.evidencia_mime,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/{incidencia_id}/avisos", response_model=BandejaAvisosDTO)
async def consultar_avisos_asignacion(
    incidencia_id: UUID,
    response: Response,
    usuario: UsuarioActual,
    session: Session,
    offset: Annotated[int, Query(ge=0, le=2_147_483_647)] = 0,
    limit: Annotated[int, Query(ge=1, le=50)] = 25,
):
    response.headers["Cache-Control"] = "private, no-store"
    return await IncidenciasService(session).listar_avisos(
        usuario, incidencia_id, offset=offset, limit=limit
    )


@router.get(
    "/{incidencia_id}/evidencia",
    response_class=Response,
    responses={
        200: {
            "content": {
                mime: {"schema": {"type": "string", "format": "binary"}}
                for mime in ("image/jpeg", "image/png")
            }
        }
    },
)
async def consultar_evidencia(incidencia_id: UUID, usuario: UsuarioActual, session: Session):
    incidencia = await IncidenciasService(session).consultar(
        usuario, incidencia_id, incluir_evidencia=True
    )
    if not incidencia.tiene_evidencia:
        raise APIError(404, "EVIDENCIA_NO_ENCONTRADA", "La incidencia no tiene evidencia adjunta.")
    return Response(
        content=incidencia.evidencia,
        media_type=incidencia.evidencia_mime,
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )
