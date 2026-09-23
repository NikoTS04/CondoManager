"""Pruebas BDD para el Dominio 04: Reservas de Áreas Comunes.

Ejecuta directamente el archivo de especificación en Gherkin:
specs/02-domains/04-reservas/features/reservas.feature
"""

from datetime import date, time
from decimal import Decimal
from pathlib import Path
import pytest

try:
    from pytest_bdd import given, parsers, scenarios, then, when
    HAS_PYTEST_BDD = True
except ImportError:
    HAS_PYTEST_BDD = False

from src.modules.reservas.service import GestorReservasService, SolicitudReservaDTO

FEATURE_FILE = (
    Path(__file__).resolve().parent.parent.parent.parent
    / "specs"
    / "02-domains"
    / "04-reservas"
    / "features"
    / "reservas.feature"
)

if HAS_PYTEST_BDD and FEATURE_FILE.exists():
    scenarios(str(FEATURE_FILE))

    @pytest.fixture
    def context():
        return {}

    @given(parsers.parse('que el departamento "{depto}" mantiene una cuota vencida en estado "EN_MORA"'))
    def depto_en_mora(context, depto):
        context["depto"] = depto
        context["deuda_mora"] = Decimal("170.00")
        context["disponible"] = True

    @given(parsers.parse('que el departamento "{depto}" se encuentra al día y sin deudas vencidas'))
    def depto_al_dia(context, depto):
        context["depto"] = depto
        context["deuda_mora"] = Decimal("0.00")
        context["disponible"] = True

    @given(parsers.parse('la "{area}" se encuentra disponible para el "{fecha}" de "{hora_inicio}" a "{hora_fin}"'))
    def area_disponible(context, area, fecha, hora_inicio, hora_fin):
        context["area"] = area
        context["fecha"] = date.fromisoformat(fecha)
        h_ini, m_ini = map(int, hora_inicio.split(":"))
        h_fin, m_fin = map(int, hora_fin.split(":"))
        context["hora_inicio"] = time(h_ini, m_ini)
        context["hora_fin"] = time(h_fin, m_fin)

    @when(parsers.parse('el residente del departamento "{depto}" intenta reservar la "{area}" para el "{fecha}" de "{hora_inicio}" a "{hora_fin}"'))
    def intentar_reservar_mora(context, depto, area, fecha, hora_inicio, hora_fin):
        h_ini, m_ini = map(int, hora_inicio.split(":"))
        h_fin, m_fin = map(int, hora_fin.split(":"))
        solicitud = SolicitudReservaDTO(
            condominio_id="vb3-condo",
            departamento_id=depto,
            usuario_id="usr-test",
            area_id=area,
            fecha_reserva=date.fromisoformat(fecha),
            hora_inicio=time(h_ini, m_ini),
            hora_fin=time(h_fin, m_fin),
        )
        context["resultado"] = GestorReservasService.validar_y_procesar_reserva(
            solicitud=solicitud,
            deuda_vencida_departamento=context["deuda_mora"],
            esta_horario_disponible=context["disponible"],
        )

    @when(parsers.parse('el residente del departamento "{depto}" solicita la reserva de dicho espacio'))
    def solicitar_reserva_solvente(context, depto):
        solicitud = SolicitudReservaDTO(
            condominio_id="vb3-condo",
            departamento_id=depto,
            usuario_id="usr-test",
            area_id=context["area"],
            fecha_reserva=context["fecha"],
            hora_inicio=context["hora_inicio"],
            hora_fin=context["hora_fin"],
        )
        context["resultado"] = GestorReservasService.validar_y_procesar_reserva(
            solicitud=solicitud,
            deuda_vencida_departamento=context["deuda_mora"],
            esta_horario_disponible=context["disponible"],
        )

    @then(parsers.parse('el sistema deniega la reserva con código de error "{error_code}"'))
    def denegar_reserva(context, error_code):
        assert context["resultado"].es_exitosa is False
        assert context["resultado"].bloqueado_por_mora is True

    @then(parsers.parse('el calendario de disponibilidad del área permanece inalterado para otros residentes'))
    def calendario_inalterado(context):
        assert context["resultado"].reserva_id is None

    @then(parsers.parse('la reserva queda registrada en estado "CONFIRMADA"'))
    def reserva_confirmada(context):
        assert context["resultado"].es_exitosa is True
        assert context["resultado"].reserva_id is not None

    @then(parsers.parse('se envía un correo de confirmación con las normas de uso del espacio'))
    def confirmacion_notificacion(context):
        pass
else:
    def test_bdd_skipped_if_no_pytest_bdd():
        """Aviso informativo si pytest-bdd no está instalado en el entorno actual."""
        if not HAS_PYTEST_BDD:
            pytest.skip("pytest-bdd no está instalado aún en el entorno global. Ejecute 'pip install pytest-bdd'.")
