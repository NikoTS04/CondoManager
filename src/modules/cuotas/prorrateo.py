"""Cálculo puro del snapshot jerárquico con cierre exacto por ítem y ámbito."""

from decimal import Decimal, localcontext
from uuid import UUID

from src.core.errors import APIError
from src.modules.cuotas.distribucion.service import cerrar_centavos
from src.shared.decimal_types import redondear_moneda


def repartir_pesos(total, pesos):
    if not pesos or any(not p.is_finite() or p <= 0 for p in pesos.values()):
        raise APIError(422, "PADRON_PRORRATEO_INVALIDO", "Se requieren participantes con peso positivo.")
    with localcontext() as ctx:
        ctx.prec = 50
        suma = sum(pesos.values(), Decimal(0))
        return cerrar_centavos({id: redondear_moneda(total * peso / suma) for id, peso in pesos.items()}, total)


def calcular_prorrateo(items, edificios, departamentos, conceptos, coberturas=None):
    bloques = {e.id: e for e in edificios}
    unidades = {e: {d.id: d for d in departamentos if d.edificio_id == e} for e in bloques}
    cuotas = {d.id: Decimal("0.00") for d in departamentos}
    detalle = []
    coberturas = coberturas or {}
    for item in items:
        concepto = conceptos.get(item.concepto_id)
        if concepto is None or not concepto.activo:
            raise APIError(422, "CONCEPTO_INVALIDO", "Seleccione conceptos activos del condominio.")
        if concepto.categoria == "OBLIGACIONES_FINANCIADAS" and item.numero_cuota is None:
            raise APIError(422, "FINANCIACION_INCOMPLETA", "Indique el cronograma de la obligación.")
        if item.metodo_asignacion == "POR_PISOS":
            asignados = repartir_pesos(item.monto_periodo, {e.id: Decimal(e.total_pisos) for e in edificios})
        elif item.metodo_asignacion == "DIRECTO_EDIFICIO":
            asignados = {item.edificio_id: item.monto_periodo}
        else:
            asignados = item.asignaciones_explicitas
        if not set(asignados).issubset(bloques):
            raise APIError(422, "EDIFICIO_AJENO", "No puede asignar gastos a otro condominio.")
        cubierto = sum((m for (iid, _), m in coberturas.items() if iid == item.id), Decimal("0.00"))
        if cubierto != item.monto_cubierto_moras:
            raise APIError(422, "COBERTURA_SIN_RESERVA", "La cobertura debe coincidir con las aplicaciones registradas.")
        if any(eid not in asignados for iid, eid in coberturas if iid == item.id):
            raise APIError(409, "COBERTURA_INCOMPATIBLE", "Libere coberturas antes de cambiar el edificio del gasto.")
        asignaciones = []
        signo = Decimal(-1 if item.tipo_movimiento == "ABONO" else 1)
        for eid, monto in sorted(asignados.items()):
            cobertura = coberturas.get((item.id, eid), Decimal("0.00"))
            if cobertura < 0 or cobertura > monto or (cobertura and signo < 0):
                raise APIError(422, "COBERTURA_EXCEDE_GASTO", "La cobertura debe financiar un cargo real de ese edificio.")
            bruto, monto = monto, monto - cobertura
            participantes = unidades[eid]
            pesos = {id: (d.coeficiente_participacion if item.metodo_unitario == "POR_ALICUOTA" else Decimal(1))
                     for id, d in participantes.items()}
            montos = repartir_pesos(monto, pesos)
            suma_pesos = sum(pesos.values())
            cargos = []
            for did, valor in sorted(montos.items()):
                cuotas[did] += valor * signo
                referencia = redondear_moneda(monto * pesos[did] / suma_pesos)
                cargos.append({"departamento_id": str(did), "monto": f"{valor * signo:.2f}",
                               "ajuste": f"{(valor - referencia) * signo:.2f}"})
            asignaciones.append({"edificio_id": str(eid), "monto": f"{monto * signo:.2f}",
                                 "monto_bruto": f"{bruto * signo:.2f}", "monto_cubierto_moras": f"{cobertura:.2f}",
                                 "unidades": len(participantes), "unitario": f"{redondear_moneda(monto / len(participantes)) * signo:.2f}",
                                 "cuotas": cargos})
        detalle.append({**item.model_dump(mode="json"), "codigo": concepto.codigo,
                        "categoria": concepto.categoria, "descripcion": item.descripcion.strip() or concepto.descripcion,
                        "asignaciones": asignaciones})
    if any(v < 0 for v in cuotas.values()):
        raise APIError(422, "CUOTA_NEGATIVA", "Resuelva el destino de los abonos excedentes antes de aprobar.")
    total = sum(cuotas.values(), Decimal("0.00"))
    if total > Decimal("9999999999.99"):
        raise APIError(422, "TOTAL_FUERA_DE_RANGO", "El total excede NUMERIC(12,2).")
    return {"items": detalle, "monto_total": f"{total:.2f}",
            "edificios": [{"id": str(e.id), "nombre": e.nombre_bloque, "pisos": e.total_pisos,
                           "departamentos": [{"id": str(d.id), "numero": d.numero,
                                              "coeficiente": str(d.coeficiente_participacion)}
                                             for d in sorted(unidades[e.id].values(), key=lambda d: d.id)]}
                          for e in sorted(edificios, key=lambda e: e.id)],
            "cuotas": {str(id): f"{monto:.2f}" for id, monto in cuotas.items()}}


def montos_snapshot(snapshot):
    return {UUID(id): Decimal(monto) for id, monto in snapshot["cuotas"].items()}
