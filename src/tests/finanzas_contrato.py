"""Aislamiento explícito para contratos históricos de identidad/calendario.

No es un fallback de producción. La aceptación financiera usa test_pagos_db.py.
"""

from contextlib import asynccontextmanager
from copy import deepcopy

import pytest
from fastapi import HTTPException

from src.core.authorization import (
    autorizar_departamento,
    contexto_consulta,
    puede_ver_departamento,
)
from src.core.errors import APIError
from src.main import app
from src.modules.pagos.persistencia import get_pagos_service
from src.modules.pagos.schemas import SolvenciaResponse
from src.modules.pagos.service import PagosService, VoucherDuplicadoException
from src.modules.pagos.solvencia import get_solvencia_service
from src.modules.usuarios.piloto import DEPARTAMENTOS_PILOTO


class FinanzasContrato:
    def __init__(self):
        self.departamentos = deepcopy(DEPARTAMENTOS_PILOTO)
        self.comprobantes = {}

    def departamento(self, did, usuario, escritura=False):
        if not puede_ver_departamento(usuario, did):
            raise HTTPException(403)
        depto = self.departamentos.get(str(did))
        if depto is None:
            raise HTTPException(404, detail={"error_code": "DEPARTAMENTO_NO_ENCONTRADO"})
        autorizar_departamento(usuario, did, depto["condominio_id"], escritura=escritura)
        if escritura and not depto["activo"]:
            raise HTTPException(403)
        return depto

    async def departamentos_portal(self, usuario, cid=None):
        cid = contexto_consulta(usuario, cid)
        return [
            d
            for d in self.departamentos.values()
            if d["condominio_id"] == cid
            and d["activo"]
            and puede_ver_departamento(usuario, d["id"])
        ]

    async def listar(self, usuario, cid=None):
        cid = contexto_consulta(usuario, cid)
        return [
            {**c, "banco": c["banco_origen"]}
            for c in self.comprobantes.values()
            if str(c["condominio_id"]) == str(cid)
            and puede_ver_departamento(usuario, c["departamento_id"])
        ]

    async def reportar(self, request, archivo, usuario):
        d = self.departamento(request.departamento_id, usuario, True)
        cantidad = len(self.comprobantes)
        try:
            resultado = PagosService.procesar_reporte_pago(
                request, str(d["condominio_id"]), self.comprobantes
            )
        except VoucherDuplicadoException as exc:
            raise APIError(409, exc.error_code, exc.mensaje) from exc
        return resultado, len(self.comprobantes) > cantidad

    @asynccontextmanager
    async def para_reserva(self, solicitud, usuario):
        d = self.departamento(solicitud.departamento_id, usuario, True)
        if d["deuda_vencida"] > 0:
            raise HTTPException(403, detail={"error_code": "DEUDA_MORA_ACTIVA"})
        yield SolvenciaResponse(
            departamento_id=d["id"], saldo_vencido=d["deuda_vencida"], habilitado_reservas=True
        )


@pytest.fixture
def finanzas_contrato(monkeypatch):
    recurso = FinanzasContrato()
    monkeypatch.setitem(app.dependency_overrides, get_pagos_service, lambda: recurso)
    monkeypatch.setitem(app.dependency_overrides, get_solvencia_service, lambda: recurso)
    return recurso
