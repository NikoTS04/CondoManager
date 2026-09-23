#!/usr/bin/env python3
"""Script de Población Semilla del Condominio Piloto: Villa Bonita 3 (139 Departamentos).

Implementa la especificación formal specs/05-operations/seed-data-spec.md:
- 139 departamentos distribuidos en 14 pisos.
- Calibración matemática exacta de alícuotas sumando 100.0000%.
- Áreas comunes (Parrillas, Salón de Eventos, Gimnasio).
- Usuarios y departamentos prototipo para pruebas funcionales.
"""

from decimal import Decimal
import sys
from typing import Dict, List


def generar_datos_departamentos() -> List[Dict]:
    """Genera la estructura de los 139 departamentos con alícuotas calibradas exactamente al 100.0000%."""
    departamentos = []
    tipo_a_count = 0
    tipo_b_count = 0

    # Pisos 1 al 13: 10 departamentos por piso (101..110, ..., 1301..1310) = 130 dptos
    for piso in range(1, 14):
        for num_correlativo in range(1, 11):
            numero = f"{piso}{num_correlativo:02d}"

            # Alternancia: departamentos impares son Tipo A (62.5 m²), pares Tipo B (75 m²)
            if num_correlativo % 2 != 0:
                coeficiente = Decimal("0.6800")
                tipo_a_count += 1
            else:
                coeficiente = Decimal("0.7400")
                tipo_b_count += 1

            departamentos.append({
                "numero": numero,
                "piso": piso,
                "coeficiente": coeficiente,
                "saldo_a_favor": Decimal("0.00"),
                "estado_financiero": "AL_DIA",
            })

    # Piso 14: 9 departamentos penthouse/dúplex (1401 al 1409)
    for num_correlativo in range(1, 10):
        numero = f"14{num_correlativo:02d}"
        if num_correlativo == 9:
            # Departamento 1409 absorbe el ajuste técnico de +0.0005% para cierre exacto al 100.0000%
            coeficiente = Decimal("0.8560")
        else:
            coeficiente = Decimal("0.8555")

        departamentos.append({
            "numero": numero,
            "piso": 14,
            "coeficiente": coeficiente,
            "saldo_a_favor": Decimal("0.00"),
            "estado_financiero": "AL_DIA",
        })

    # Casos prototipo para pruebas funcionales según seed-data-spec.md
    for depto in departamentos:
        if depto["numero"] == "302":
            # Dpto 302: Cuenta con saldo a favor de S/ 200.00
            depto["saldo_a_favor"] = Decimal("200.00")
        elif depto["numero"] == "402":
            # Dpto 402: Residente moroso bloqueado para reservas
            depto["estado_financiero"] = "EN_MORA"
        elif depto["numero"] == "504":
            # Dpto 504: Residente con pago en revisión
            depto["estado_financiero"] = "OBSERVADO"

    return departamentos


def generar_datos_areas_comunes() -> List[Dict]:
    """Genera las 4 áreas comunes del condominio piloto."""
    return [
        {
            "nombre": "Zona de Parrilla 1 (Terraza Piso 15)",
            "descripcion": "Parrilla de acero inoxidable con mesa para 12 comensales.",
            "aforo_maximo": 12,
            "costo_reserva": Decimal("25.00"),
        },
        {
            "nombre": "Zona de Parrilla 2 (Terraza Piso 15)",
            "descripcion": "Parrilla de acero inoxidable con mesa para 12 comensales.",
            "aforo_maximo": 12,
            "costo_reserva": Decimal("25.00"),
        },
        {
            "nombre": "Salón Social de Eventos (Piso 1)",
            "descripcion": "Salón climatizado para reuniones y cumpleaños con cocina de apoyo.",
            "aforo_maximo": 40,
            "costo_reserva": Decimal("100.00"),
        },
        {
            "nombre": "Sala Fitness / Gimnasio (Piso 1)",
            "descripcion": "Máquinas cardiovasculares y mancuernas para residentes.",
            "aforo_maximo": 8,
            "costo_reserva": Decimal("0.00"),
        },
    ]


def verificar_dataset_piloto():
    deptos = generar_datos_departamentos()
    total_unidades = len(deptos)
    suma_alicuotas = sum(d["coeficiente"] for d in deptos)

    print(f"Total unidades generadas: {total_unidades}")
    print(f"Sumatoria de alícuotas calculada: {suma_alicuotas}%")

    if total_unidades != 139:
        print(f"❌ Error: Se esperaban 139 departamentos, se obtuvieron {total_unidades}")
        sys.exit(1)

    if suma_alicuotas != Decimal("100.0000"):
        print(f"❌ Error: La suma de alícuotas debe ser 100.0000%, obtenido: {suma_alicuotas}")
        sys.exit(1)

    print("✅ Calibración matemática exitosa: 139 departamentos sumando exactamente 100.0000% de alícuota.")


if __name__ == "__main__":
    verificar_dataset_piloto()
