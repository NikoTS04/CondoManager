"""Catálogo contextual y previsualización del mismo detalle que emite las cuotas."""

from copy import deepcopy
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from src.core.audit import AuditoriaPayload
from src.core.authorization import autorizar_condominio, vinculos_activos
from src.core.database import get_db_session
from src.core.errors import APIError
from src.core.models_audit import AuditoriaLogORM
from src.core.security import get_current_user
from src.modules.condominios.models import Condominio, Departamento
from src.modules.cuotas.documentos_prorrateo import generar_documento
from src.modules.cuotas.presupuestos.models import ConceptoPresupuestal, PresupuestoMensual
from src.modules.cuotas.presupuestos.repository import SQLAlchemyPresupuestoRepository
from src.modules.cuotas.prorrateo_schemas import ConceptoRequest, ConceptoResponse

router = APIRouter(tags=["Prorrateo mensual"])


def acceso_administrativo(actor, cid, escritura=False):
    autorizar_condominio(actor, cid, escritura=escritura)
    if actor.get("rol") not in {"SUPERADMIN", "ADMIN_JUNTA", "AUDITOR"}:
        raise APIError(403, "ACCESO_DENEGADO", "Operación administrativa.")


@router.get(
    "/condominios/{condominio_id}/conceptos-presupuestales", response_model=list[ConceptoResponse]
)
async def listar_conceptos(
    condominio_id: UUID,
    actor=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, use_cache=False),
):
    acceso_administrativo(actor, condominio_id)
    async with session.begin():
        if await session.get(Condominio, condominio_id) is None:
            raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe el condominio.")
        return list(
            await session.scalars(
                select(ConceptoPresupuestal)
                .where(ConceptoPresupuestal.condominio_id == condominio_id)
                .order_by(ConceptoPresupuestal.codigo)
            )
        )


@router.post(
    "/condominios/{condominio_id}/conceptos-presupuestales",
    response_model=ConceptoResponse,
    status_code=201,
)
async def crear_concepto(
    condominio_id: UUID,
    request: ConceptoRequest,
    actor=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, use_cache=False),
):
    acceso_administrativo(actor, condominio_id, escritura=True)
    async with session.begin():
        condominio = await session.scalar(
            select(Condominio).where(Condominio.id == condominio_id).with_for_update()
        )
        if condominio is None or not condominio.activo:
            raise APIError(404, "CONDOMINIO_NO_ENCONTRADO", "No existe un condominio activo.")
        if (
            await session.scalar(
                select(ConceptoPresupuestal.id).where(
                    ConceptoPresupuestal.condominio_id == condominio_id,
                    ConceptoPresupuestal.codigo == request.codigo,
                )
            )
            is not None
        ):
            raise APIError(409, "CONCEPTO_DUPLICADO", "El código ya existe en este condominio.")
        concepto = ConceptoPresupuestal(
            id=uuid4(), condominio_id=condominio_id, activo=True, **request.model_dump()
        )
        session.add(concepto)
        previo = await SQLAlchemyPresupuestoRepository(session).obtener_ultimo_hash_auditoria(
            condominio_id
        )
        posterior = ConceptoResponse.model_validate(concepto).model_dump(mode="json")
        payload = AuditoriaPayload(
            condominio_id=str(condominio_id),
            departamento_id=None,
            accion_ejecutada="CONCEPTO_PRESUPUESTAL_CREADO",
            motivo="ALTA_CATALOGO_PRESUPUESTAL",
            resultado="EXITOSO",
            actor_tipo=actor["rol"],
            actor_id=str(actor["sub"]),
            estado_anterior={},
            estado_posterior=posterior,
            hash_previo=previo,
        )
        session.add(
            AuditoriaLogORM(
                condominio_id=condominio_id,
                departamento_id=None,
                timestamp=payload.timestamp,
                accion_ejecutada=payload.accion_ejecutada,
                motivo=payload.motivo,
                resultado=payload.resultado,
                actor_tipo=payload.actor_tipo,
                actor_id=payload.actor_id,
                estado_anterior={},
                estado_posterior=posterior,
                hash_previo=previo,
                hash_actual=payload.calcular_hash(),
            )
        )
        await session.flush()
        return concepto


@router.get("/presupuestos/{presupuesto_id}/prorrateo")
async def consultar_prorrateo(
    presupuesto_id: UUID,
    edificio_id: UUID | None = None,
    actor=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, use_cache=False),
):
    async with session.begin():
        p = await session.get(PresupuestoMensual, presupuesto_id)
        if p is None:
            raise APIError(404, "PRESUPUESTO_NO_ENCONTRADO", "No existe el presupuesto.")
        autorizar_condominio(actor, p.condominio_id)
        residente = actor.get("rol") == "RESIDENTE"
        if residente:
            if p.estado != "APROBADO" or edificio_id is None:
                raise APIError(
                    403, "ACCESO_DENEGADO", "Seleccione un edificio propio con reporte aprobado."
                )
            propias = [UUID(id) for id in vinculos_activos(actor)]
            permitido = await session.scalar(
                select(Departamento.id)
                .where(
                    Departamento.id.in_(propias),
                    Departamento.edificio_id == edificio_id,
                    Departamento.activo.is_(True),
                )
                .limit(1)
            )
            if permitido is None:
                raise APIError(
                    403, "ACCESO_DENEGADO", "El edificio no pertenece a sus vínculos activos."
                )
        else:
            acceso_administrativo(actor, p.condominio_id)
        if p.items is None:
            raise APIError(
                409,
                "PRESUPUESTO_SIN_DETALLE",
                "El presupuesto histórico no tiene detalle reconstruido.",
            )
        if p.estado == "BORRADOR":
            p = await SQLAlchemyPresupuestoRepository(session).obtener_por_id(
                p.id, p.condominio_id, bloquear=True
            )
        snapshot = (
            deepcopy(p.prorrateo_snapshot)
            if p.prorrateo_snapshot is not None
            else await SQLAlchemyPresupuestoRepository(session).preparar_detalle(
                p.condominio_id, p.items, p.id
            )
        )
        if edificio_id is not None:
            snapshot["edificios"] = [
                e for e in snapshot["edificios"] if e["id"] == str(edificio_id)
            ]
            if not snapshot["edificios"]:
                raise APIError(
                    404, "EDIFICIO_NO_ENCONTRADO", "El edificio no pertenece al reporte."
                )
            ids = {d["id"] for e in snapshot["edificios"] for d in e["departamentos"]}
            snapshot["cuotas"] = {
                id: monto for id, monto in snapshot["cuotas"].items() if id in ids
            }
            for item in snapshot["items"]:
                item["asignaciones"] = [
                    a for a in item["asignaciones"] if a["edificio_id"] == str(edificio_id)
                ]
            snapshot["items"] = [i for i in snapshot["items"] if i["asignaciones"]]
            snapshot["monto_total"] = (
                f"{sum((Decimal(m) for m in snapshot['cuotas'].values()), Decimal('0.00')):.2f}"
            )
            if "fondos_moras" in snapshot:
                snapshot["fondos_moras"] = [
                    f for f in snapshot["fondos_moras"] if f["edificio_id"] == str(edificio_id)
                ]
        if residente:
            snapshot.pop("cuotas")
            for e in snapshot["edificios"]:
                e["unidades"] = len(e.pop("departamentos"))
            publicos = {
                "id",
                "codigo",
                "descripcion",
                "seccion",
                "tipo_movimiento",
                "monto_periodo",
                "metodo_asignacion",
                "metodo_unitario",
                "asignaciones",
            }
            for item in snapshot["items"]:
                for a in item["asignaciones"]:
                    a.pop("cuotas")
                for campo in set(item) - publicos:
                    item.pop(campo)
        return {
            "presupuesto_id": str(p.id),
            "version": p.version,
            "periodo": p.periodo,
            "aprobado_por": p.aprobado_por,
            "aprobado_en": p.aprobado_en.isoformat() if p.aprobado_en else None,
            "moneda": p.moneda,
            "estado": p.estado,
            "fecha_vencimiento": p.fecha_vencimiento,
            **snapshot,
        }


@router.get("/presupuestos/{presupuesto_id}/prorrateo/exportar")
async def exportar_prorrateo(
    presupuesto_id: UUID,
    version: int = Query(ge=1),
    formato: Literal["pdf", "docx"] = "pdf",
    edificio_id: UUID | None = None,
    actor=Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session, use_cache=False),
):
    reporte = await consultar_prorrateo(presupuesto_id, edificio_id, actor, session)
    if reporte["version"] != version:
        raise APIError(
            409, "PRESUPUESTO_VERSION_OBSOLETA", "El reporte cambió. Recargue antes de exportar."
        )
    try:
        contenido = await run_in_threadpool(generar_documento, reporte, formato)
    except Exception as exc:
        raise APIError(
            503, "EXPORTACION_NO_DISPONIBLE", "No se pudo generar el documento. Intente nuevamente."
        ) from exc
    mime = (
        "application/pdf"
        if formato == "pdf"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    nombre = f"Prorrateo_{reporte['periodo']}_{edificio_id or 'condominio'}_v{version}.{formato}"
    return Response(
        contenido,
        media_type=mime,
        headers={
            "Content-Disposition": f'attachment; filename="{nombre}"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )
