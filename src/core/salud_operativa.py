"""CON-68: salud por componente y última ejecución de jobs, solo lectura.

Reutiliza las comprobaciones de `health.py`; nunca devuelve URLs, credenciales ni errores del
driver. La lectura de ejecuciones de jobs está aislada en `listar_ejecuciones_jobs` para que
CON-83 la sustituya por su registro completo sin cambiar el contrato de la vista.
"""

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime

from src.core.config import settings
from src.core.health import comprobar_postgres, estado_dependencia, estado_redis

# Jobs que existen hoy en src/core/jobs.py; los que no tengan registro figuran SIN_REGISTRO.
JOBS_CONOCIDOS = ("notificaciones", "diario")
# estado_job_notificaciones guarda el job de notificaciones con el nombre histórico "correo".
NOMBRE_JOB_REGISTRADO = {"correo": "notificaciones"}
SIN_REGISTRO = "SIN_REGISTRO"


@dataclass(frozen=True)
class EjecucionJob:
    """Interfaz que debe devolver cualquier fuente de ejecuciones (CON-83).

    Una fila por job con su última ejecución. `duracion_segundos` es None mientras no hay fin.
    `resultado`: EN_CURSO, COMPLETADO, INCOMPLETO o SIN_REGISTRO.
    """

    nombre: str
    inicio: datetime | None
    fin: datetime | None
    duracion_segundos: float | None
    resultado: str


def _ejecucion(nombre, inicio, fin, resultado):
    duracion = (fin - inicio).total_seconds() if inicio and fin else None
    return EjecucionJob(nombre, inicio, fin, duracion, resultado)


async def listar_ejecuciones_jobs(db) -> list[EjecucionJob]:
    """Última ejecución por job desde `estado_job_notificaciones` (fuente actual).

    Sustituir el cuerpo por el registro de CON-83 manteniendo la firma y el tipo devuelto.
    """
    from sqlalchemy import select

    from src.modules.notificaciones.models import EstadoJobNotificaciones

    filas = (await db.execute(select(EstadoJobNotificaciones))).scalars().all()
    por_nombre = {
        NOMBRE_JOB_REGISTRADO.get(f.nombre, f.nombre): _ejecucion(
            NOMBRE_JOB_REGISTRADO.get(f.nombre, f.nombre), f.inicio, f.fin, f.estado
        )
        for f in filas
    }
    for nombre in JOBS_CONOCIDOS:
        por_nombre.setdefault(nombre, EjecucionJob(nombre, None, None, None, SIN_REGISTRO))
    orden = {n: i for i, n in enumerate(JOBS_CONOCIDOS)}
    return sorted(por_nombre.values(), key=lambda e: (orden.get(e.nombre, len(orden)), e.nombre))


async def estado_componentes() -> list[dict]:
    """Estado de API, PostgreSQL y servicios esenciales según el perfil del ambiente."""
    postgres, redis = await asyncio.gather(estado_dependencia(comprobar_postgres), estado_redis())
    return [
        {"componente": "api", "estado": "ok"},
        {"componente": "postgresql", "estado": postgres},
        {"componente": "redis", "estado": "deshabilitado" if redis == "disabled" else redis},
        {
            "componente": "correo",
            # Configuración, no sondeo: esta vista no contacta al proveedor.
            "estado": "ok" if settings.MAILJET_ENABLED else "deshabilitado",
        },
    ]


async def salud_operativa(db) -> dict:
    componentes = await estado_componentes()
    try:
        async with db.begin():
            jobs = await listar_ejecuciones_jobs(db)
    except Exception:
        # Sin PostgreSQL no hay registro de jobs; la vista debe seguir mostrando la caída.
        jobs = [EjecucionJob(n, None, None, None, SIN_REGISTRO) for n in JOBS_CONOCIDOS]
    return {
        "perfil": settings.APP_ENV,
        "estado_general": "degradado" if any(c["estado"] == "error" for c in componentes) else "ok",
        "generado_en": datetime.now(UTC),
        "componentes": componentes,
        "jobs": [vars(j) for j in jobs],
    }
