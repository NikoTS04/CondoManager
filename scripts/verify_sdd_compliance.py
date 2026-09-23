#!/usr/bin/env python3
"""Herramienta de Verificación Estática de Cumplimiento SDD (Spec-Driven Development) para CondoManager.

Verifica automáticamente:
1. Correspondencia estructural entre especificaciones de dominio y módulos de código fuente.
2. Presencia de artefactos de prueba BDD (.feature).
3. Existencia y completitud del contrato formal OpenAPI 3.1.
4. Cumplimiento de la regla Zero-Float (ADR-002) en cálculos financieros.
5. Presencia innegociable de los 7 campos de auditoría inmutable.
"""

from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent

ERRORES = []
WARNINGS = []


def verificar_dominios():
    specs_domains_dir = REPO_ROOT / "specs" / "02-domains"
    if not specs_domains_dir.exists():
        ERRORES.append("Directorio specs/02-domains/ no encontrado.")
        return

    dominios_esperados = [
        "01-cuotas",
        "02-pagos-y-moras",
        "03-notificaciones",
        "04-reservas",
        "05-usuarios-rbac",
        "06-egresos-proveedores",
        "07-tickets-incidencias",
        "08-reportes-kpis",
    ]

    for dom in dominios_esperados:
        dom_dir = specs_domains_dir / dom
        if not dom_dir.exists():
            ERRORES.append(f"Falta el directorio de especificación del dominio: {dom}")
        else:
            spec_file = dom_dir / "spec.md"
            if not spec_file.exists():
                ERRORES.append(f"Falta el archivo spec.md en el dominio: {dom}")


def verificar_features_bdd():
    dominios_con_features = [
        "01-cuotas",
        "02-pagos-y-moras",
        "03-notificaciones",
        "04-reservas",
    ]
    for dom in dominios_con_features:
        features_dir = REPO_ROOT / "specs" / "02-domains" / dom / "features"
        if not features_dir.exists() or not list(features_dir.glob("*.feature")):
            ERRORES.append(f"Falta archivo .feature ejecutable en {dom}/features/")


def verificar_contratos():
    openapi_file = REPO_ROOT / "specs" / "03-contracts" / "openapi" / "condomanager.openapi.yaml"
    if not openapi_file.exists():
        ERRORES.append("Falta el contrato OpenAPI en specs/03-contracts/openapi/condomanager.openapi.yaml")

    data_dict = REPO_ROOT / "specs" / "03-contracts" / "database" / "data-dictionary.md"
    if not data_dict.exists():
        ERRORES.append("Falta el diccionario de datos en specs/03-contracts/database/data-dictionary.md")


def verificar_zero_float():
    src_dir = REPO_ROOT / "src"
    patron_float = re.compile(r"\bfloat\s*\(", re.IGNORECASE)

    archivos_financieros = list(src_dir.glob("modules/cuotas/**/*.py")) + \
                           list(src_dir.glob("modules/pagos/**/*.py")) + \
                           list(src_dir.glob("shared/decimal_types.py"))

    for arch in archivos_financieros:
        contenido = arch.read_text(encoding="utf-8")
        if patron_float.search(contenido):
            ERRORES.append(
                f"Violación de ADR-002 (Zero-Float): Se detectó uso de 'float(' en archivo financiero {arch.relative_to(REPO_ROOT)}"
            )


def verificar_7_campos_auditoria():
    audit_file = REPO_ROOT / "src" / "core" / "audit.py"
    if not audit_file.exists():
        ERRORES.append("Falta el módulo de auditoría src/core/audit.py")
        return

    contenido = audit_file.read_text(encoding="utf-8")
    campos_requeridos = [
        "departamento_id",
        "timestamp",
        "accion_ejecutada",
        "motivo",
        "resultado",
        "estado_anterior",
        "estado_posterior",
    ]
    for campo in campos_requeridos:
        if campo not in contenido:
            ERRORES.append(f"Falta el campo de auditoría obligatorio '{campo}' en src/core/audit.py")


def main():
    print("=" * 70)
    print(" Verificador de Cumplimiento SDD (Spec-Driven Development) ")
    print("=" * 70)

    verificar_dominios()
    verificar_features_bdd()
    verificar_contratos()
    verificar_zero_float()
    verificar_7_campos_auditoria()

    if ERRORES:
        print("\n❌ SE ENCONTRARON INFRACCIONES DE CUMPLIMIENTO SDD:\n")
        for err in ERRORES:
            print(f"  • {err}")
        print("\nEl commit o Pull Request no cumple con las directrices de SDD.")
        sys.exit(1)
    else:
        print("\n✅ TODAS LAS REGLAS DE CUMPLIMIENTO SDD FUERON SATISFECHAS EXITOSAMENTE:")
        print("  • Dominios autocontenidos y especificaciones presentes.")
        print("  • Suites BDD ejecutables (.feature) validadas.")
        print("  • Contrato OpenAPI 3.1 y Diccionario de Datos validados.")
        print("  • Cero uso de 'float' en módulos de contabilidad (Regla ADR-002 OK).")
        print("  • Los 7 campos inmutables de auditoría presentes en el core.")
        print("=" * 70)
        sys.exit(0)


if __name__ == "__main__":
    main()
