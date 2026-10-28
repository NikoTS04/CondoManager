"""Reconstrucción determinista: mora sin capitalización y pagos por fecha bancaria."""

from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from uuid import UUID

from src.core.errors import APIError
from src.modules.pagos.contabilidad import CERO, MAX_MONEDA, plan_imputacion

COMPONENTES = ("MORA", "EXTRAORDINARIA", "ORDINARIA")


@dataclass
class CuotaCalculo:
    id: UUID
    periodo: str
    fecha_emision: date
    fecha_vencimiento: date
    monto_total_exigible: Decimal
    monto_extraordinario: Decimal
    monto_mora: Decimal
    monto_pagado: Decimal
    politica_mora_aplicada: dict | None


def es_diaria(cuota):
    return (cuota.politica_mora_aplicada or {}).get("modalidad") == "MONTO_DIARIO"


def politica_diaria(cuota):
    p = cuota.politica_mora_aplicada
    try:
        importe = Decimal(p["monto_diario"])
        gracia = p["dias_gracia"]
        if (not importe.is_finite() or not CERO < importe <= MAX_MONEDA
                or importe.as_tuple().exponent < -2 or type(gracia) is not int
                or not 0 <= gracia <= 30 or p["zona_horaria"] != "America/Lima"):
            raise ValueError
    except (InvalidOperation, KeyError, TypeError, ValueError) as exc:
        raise APIError(409, "SNAPSHOT_DIARIO_INVALIDO", "Revise la política histórica de la cuota.") from exc
    return importe, gracia


def reconstruir(cuotas, pagos, hasta, limites=None, alcances=None):
    """Entradas ya validadas/normalizadas; no muta ORM ni recibos históricos.

    monto_pagado es amortización anterior al ledger diario: permanece fija.
    Los límites opcionales postergan solo nuevos devengos durante la pausa de 24 h.
    """
    cuotas = [replace(c) for c in cuotas]
    pagados = {}
    cursores, politicas, devengos, movimientos = {}, {}, {}, {}
    for c in cuotas:
        mora = min(c.monto_mora, c.monto_total_exigible)
        extra = min(c.monto_extraordinario, c.monto_total_exigible - mora)
        ordinaria = c.monto_total_exigible - mora - extra
        resto = c.monto_pagado
        pagados[c.id] = []
        for bruto in (mora, extra, ordinaria):
            cubierto = min(resto, bruto)
            pagados[c.id].append(cubierto)
            resto -= cubierto
        if resto != CERO:
            raise APIError(409, "BASE_FINANCIERA_INVALIDA", "Las amortizaciones históricas no cuadran.")
        if es_diaria(c):
            politicas[c.id] = politica_diaria(c)
            cursores[c.id] = max(c.fecha_emision, c.fecha_vencimiento + timedelta(days=politicas[c.id][1] + 1))

    def devengar(fecha):
        for c in cuotas:
            if c.id not in politicas:
                continue
            importe, _ = politicas[c.id]
            limite = min(fecha, (limites or {}).get(c.id, hasta))
            principal = c.monto_total_exigible - c.monto_mora
            if pagados[c.id][1] + pagados[c.id][2] >= principal:
                continue
            while cursores[c.id] <= limite:
                devengos[c.id, cursores[c.id]] = importe
                c.monto_mora += importe
                c.monto_total_exigible += importe
                cursores[c.id] += timedelta(days=1)
            if c.monto_total_exigible > MAX_MONEDA:
                raise APIError(422, "MORA_FUERA_DE_RANGO", "La deuda excede NUMERIC(12,2).")

    for p in sorted(pagos, key=lambda p: (p.fecha_operacion, p.id.int)):
        if p.fecha_operacion > hasta:
            raise APIError(422, "FECHA_BANCARIA_FUTURA", "La fecha bancaria no puede ser futura en Lima.")
        devengar(p.fecha_operacion)
        plan = plan_imputacion([c for c in cuotas if c.fecha_emision <= p.fecha_operacion
                               and (alcances is None or c.id in alcances[p.id])],
                              p.monto, p.fecha_operacion, pagados)
        for cid, importes in plan["componentes"].items():
            for i, importe in enumerate(importes):
                if importe:
                    movimientos[p.id, cid, COMPONENTES[i]] = importe
                    pagados[cid][i] += importe
        if plan["remanente"]:
            movimientos[p.id, None, "CREDITO"] = plan["remanente"]
    devengar(hasta)
    return {"devengos": devengos, "movimientos": movimientos,
            "cuotas": {c.id: {"mora": c.monto_mora, "total": c.monto_total_exigible,
                              "pagado": sum(pagados[c.id], CERO)} for c in cuotas}}
