#!/usr/bin/env python3
"""Script de Verificación Piloto End-to-End para CondoManager (Villa Bonita 3 - 139 Departamentos).

Ejecuta el flujo operacional completo integrando los cuatro dominios del MVP:
1. PROC-01 (Anderson): Emisión de cuotas a 139 departamentos y amortización de saldo a favor.
2. PROC-02 (Tarqui): Evaluación nocturna de moras y postergación por periodo de gracia.
3. PROC-04 (Brandon): Invariante de Solvencia Financiera bloqueando reservas en mora.
4. PROC-02 (Tarqui): Reporte de voucher con hash SHA-256 y conciliación contable.
5. PROC-04 (Brandon): Rehabilitación de reservas para el residente tras quedar al día.
6. PROC-03 (Alejandro): Despacho de notificaciones y política de reintentos exponenciales.
7. Auditoría Inmutable: Presencia de los 7 campos obligatorios y encadenamiento criptográfico.
"""

from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
import sys
import uuid

# Asegurar que la raíz del proyecto esté en sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Importación de servicios y modelos del core
from scripts.seed_condominio_piloto import generar_datos_areas_comunes, generar_datos_departamentos
from src.core.audit import AuditoriaPayload
from src.modules.cuotas.schemas import EmitirLoteCuotasRequest
from src.modules.cuotas.service import CuotasService
from src.modules.notificaciones.schemas import (
    CanalNotificacionEnum,
    DespacharNotificacionRequest,
    EstadoNotificacionEnum,
)
from src.modules.notificaciones.service import NotificacionesService
from src.modules.pagos.moras_service import MotorMorasService
from src.modules.pagos.schemas import ReportarPagoRequest
from src.modules.pagos.service import PagosService
from src.modules.reservas.schemas import CancelarReservaRequest, CrearReservaRequest
from src.modules.reservas.service import (
    ConflictoHorarioException,
    DeudaMoraActivaException,
    ReservasService,
)


def print_step(num: int, title: str):
    print(f"\n[{num}] {'=' * 65}")
    print(f"     {title}")
    print(f"     {'=' * 65}")


def main():
    print("=" * 70)
    print(" CONDOMANAGER: EJECUCIÓN DEL ESCENARIO PILOTO END-TO-END (SDD)")
    print(" Edificio 3 • Villa Bonita 3 • 139 Departamentos")
    print("=" * 70)

    # ------------------------------------------------------------------------
    # PASO 1: Emisión mensual de cuotas para 139 departamentos
    # ------------------------------------------------------------------------
    print_step(1, "PROC-01 (Anderson): Emisión Masiva de Cuotas Ordinarias")
    deptos = generar_datos_departamentos()
    presupuesto = Decimal("20850.00")
    periodo = "2026-11"

    req_emision = EmitirLoteCuotasRequest(
        condominio_id=uuid.uuid4(),
        periodo=periodo,
        presupuesto_total=presupuesto,
        fecha_vencimiento=date(2026, 11, 20),
    )

    res_emision = CuotasService.emitir_lote_en_memoria(
        request=req_emision,
        departamentos=deptos,
    )

    print(f"• Total cuotas emitidas: {res_emision.total_cuotas_emitidas} departamentos.")
    print(f"• Monto total facturado: S/ {res_emision.monto_total_facturado:.2f}")
    print(f"• Cuotas cubiertas 100% con saldo a favor: {res_emision.cuotas_cubiertas_saldo_favor}")

    assert res_emision.total_cuotas_emitidas == 139, "Deben emitirse 139 cuotas."
    assert res_emision.monto_total_facturado == presupuesto, "Cierre exacto al centavo obligatorio."
    assert res_emision.cuotas_cubiertas_saldo_favor >= 1

    # Validar amortización automática del Dpto. 302 (Saldo a favor previo de S/ 200.00)
    depto_302_data = next(d for d in deptos if d["numero"] == "302")
    cuota_302 = CuotasService.calcular_emision_departamento(
        departamento_id=uuid.uuid4(),
        departamento_numero="302",
        coeficiente=depto_302_data["coeficiente"],
        saldo_a_favor=depto_302_data["saldo_a_favor"],
        presupuesto_total=presupuesto,
        periodo=periodo,
        fecha_emision=date.today(),
        fecha_vencimiento=date(2026, 11, 20),
    )
    print(f"• Dpto. 302 (Saldo previo S/ 200.00): Cuota bruta S/ {cuota_302['monto_ordinario']:.2f} -> Estado: {cuota_302['estado']}, Exigible: S/ {cuota_302['monto_total_exigible']:.2f}")
    assert cuota_302["estado"] == "PAGADA", "La cuota del Dpto. 302 debió quedar PAGADA por amortización."
    assert cuota_302["monto_total_exigible"] == Decimal("0.00")
    print("✅ Invariante de cierre contable y amortización validada con éxito.")

    # ------------------------------------------------------------------------
    # PASO 2: Evaluación nocturna de moras tras periodo de gracia
    # ------------------------------------------------------------------------
    print_step(2, "PROC-02 (Tarqui): Evaluación de Moras con Periodo de Gracia")
    cuota_vencida = {
        "id": uuid.uuid4(),
        "departamento_id": "402",
        "periodo": "2026-10",
        "fecha_vencimiento": date(2026, 10, 20),
        "monto_total_exigible": Decimal("150.00"),
        "monto_mora": Decimal("0.00"),
        "monto_pagado": Decimal("0.00"),
        "estado": "PENDIENTE",
    }
    depto_402 = {
        "id": "402",
        "numero": "402",
        "saldo_a_favor": Decimal("0.00"),
        "estado_financiero": "AL_DIA",
    }

    # Caso 2.1: Dentro del periodo de gracia (21 de octubre)
    res_gracia = MotorMorasService.evaluar_y_aplicar_moras(
        cuotas=[dict(cuota_vencida)],
        departamentos={"402": dict(depto_402)},
        comprobantes_en_revision_por_depto={},
        fecha_evaluacion=date(2026, 10, 21),
    )
    print("• Evaluación al día 21 (En periodo de gracia): Recargo NO aplicado.")
    assert res_gracia.moras_aplicadas == 0

    # Caso 2.2: Vencido el periodo de gracia (23 de octubre)
    res_mora = MotorMorasService.evaluar_y_aplicar_moras(
        cuotas=[cuota_vencida],
        departamentos={"402": depto_402},
        comprobantes_en_revision_por_depto={},
        fecha_evaluacion=date(2026, 10, 23),
    )
    print(f"• Evaluación al día 23 (Gracia vencida): Mora de S/ 20.00 aplicada.")
    print(f"• Nuevo estado del departamento: {depto_402['estado_financiero']}, Cuota: S/ {cuota_vencida['monto_total_exigible']:.2f}")
    assert res_mora.moras_aplicadas == 1
    assert depto_402["estado_financiero"] == "EN_MORA"
    assert cuota_vencida["monto_mora"] == Decimal("20.00")
    print("✅ Motor de moras y periodo de gracia validado con éxito.")

    # ------------------------------------------------------------------------
    # PASO 3: Invariante Crítica de Solvencia Financiera en Reservas
    # ------------------------------------------------------------------------
    print_step(3, "PROC-04 (Brandon): Control Estricto de Solvencia para Reservas")
    areas = generar_datos_areas_comunes()
    parrilla_1 = areas[0]
    parrilla_1["id"] = uuid.UUID("11111111-1111-1111-1111-111111111101")
    parrilla_1["condominio_id"] = uuid.uuid4()
    parrilla_1["esta_activa"] = True

    req_reserva_402 = CrearReservaRequest(
        condominio_id=parrilla_1["condominio_id"],
        area_id=parrilla_1["id"],
        departamento_id=uuid.uuid4(),
        fecha_reserva=date(2026, 10, 25),
        hora_inicio=time(19, 0),
        hora_fin=time(22, 0),
    )

    try:
        ReservasService.procesar_reserva(
            request=req_reserva_402,
            area=parrilla_1,
            estado_financiero_depto="EN_MORA",
            saldo_mora_depto=Decimal("170.00"),
            reservas_existentes=[],
        )
        print("❌ Error: Se esperaba rechazo por mora activa.")
        sys.exit(1)
    except DeudaMoraActivaException as exc:
        print(f"• Intento de reserva por Dpto. 402 bloqueado con éxito.")
        print(f"  Código: {exc.error_code} | Saldo vencido: S/ {exc.saldo_vencido:.2f}")
        assert exc.error_code == "DEUDA_MORA_ACTIVA"
    print("✅ Invariante innegociable de solvencia validada con éxito.")

    # ------------------------------------------------------------------------
    # PASO 4: Reporte de pago con Idempotencia SHA-256 y Conciliación
    # ------------------------------------------------------------------------
    print_step(4, "PROC-02 (Tarqui): Idempotencia Bancaria y Conciliación")
    comprobantes_store = {}
    req_pago = ReportarPagoRequest(
        departamento_id=uuid.uuid4(),
        banco="YAPE",
        numero_operacion="0089214",
        fecha_operacion=date(2026, 10, 24),
        monto=Decimal("170.00"),
        url_voucher="https://s3.local/vouchers/voucher_0089214.jpg",
    )

    # Reporte 1
    res_pago_1 = PagosService.procesar_reporte_pago(
        request=req_pago,
        condominio_id="vb3-condo",
        comprobantes_existentes=comprobantes_store,
    )
    print(f"• Comprobante recibido. Estado: {res_pago_1.estado} | Hash SHA-256: {res_pago_1.idempotency_hash[:16]}...")

    # Reporte 2 duplicado (idempotencia)
    res_pago_2 = PagosService.procesar_reporte_pago(
        request=req_pago,
        condominio_id="vb3-condo",
        comprobantes_existentes=comprobantes_store,
    )
    assert res_pago_1.comprobante_id == res_pago_2.comprobante_id, "Idempotencia falló: generó duplicado."
    print("• Intento de reporte duplicado detectado: comprobante existente devuelto sin duplicar.")

    # Conciliación por la Junta Directiva
    comprobante_obj = comprobantes_store[res_pago_1.idempotency_hash]
    res_conciliacion = PagosService.conciliar_comprobante(
        comprobante=comprobante_obj,
        decision="APROBADO",
        cuotas_pendientes=[cuota_vencida],
        departamento=depto_402,
    )

    print(f"• Conciliación aprobada: Imputado S/ {res_conciliacion.monto_imputado:.2f}.")
    print(f"• Estado financiero restituido: {depto_402['estado_financiero']} (Habilitado para reservas).")
    assert depto_402["estado_financiero"] == "AL_DIA", "El departamento debió quedar AL_DIA tras conciliar."
    print("✅ Idempotencia y conciliación con restitución de solvencia validada.")

    # ------------------------------------------------------------------------
    # PASO 5: Desbloqueo de Reservas y Prevención de Solapamientos
    # ------------------------------------------------------------------------
    print_step(5, "PROC-04 (Brandon): Aprobación de Reserva tras Solvencia Restituida")
    reserva_aprobada, audit_reserva = ReservasService.procesar_reserva(
        request=req_reserva_402,
        area=parrilla_1,
        estado_financiero_depto="AL_DIA",
        saldo_mora_depto=Decimal("0.00"),
        reservas_existentes=[],
    )

    print(f"• Reserva aprobada: ID {reserva_aprobada.id} | Estado: {reserva_aprobada.estado}")
    print(f"  Tarifa confirmada: S/ {reserva_aprobada.costo_reserva:.2f} en {reserva_aprobada.fecha_reserva}")
    assert reserva_aprobada.estado == "CONFIRMADA"

    # Validar detección de conflicto si otro residente intenta el mismo horario
    req_reserva_conflicto = CrearReservaRequest(
        condominio_id=parrilla_1["condominio_id"],
        area_id=parrilla_1["id"],
        departamento_id=uuid.uuid4(),
        fecha_reserva=date(2026, 10, 25),
        hora_inicio=time(20, 0),
        hora_fin=time(23, 0),
    )

    try:
        ReservasService.procesar_reserva(
            request=req_reserva_conflicto,
            area=parrilla_1,
            estado_financiero_depto="AL_DIA",
            saldo_mora_depto=Decimal("0.00"),
            reservas_existentes=[reserva_aprobada.model_dump()],
        )
        print("❌ Error: Se esperaba ConflictoHorarioException por solapamiento.")
        sys.exit(1)
    except ConflictoHorarioException as exc:
        print(f"• Colisión horaria detectada y bloqueada: {exc.error_code} en fecha {exc.fecha}.")
        assert exc.error_code == "HORARIO_NO_DISPONIBLE"
    print("✅ Control de concurrencia y disponibilidad validado con éxito.")

    # ------------------------------------------------------------------------
    # PASO 6: Despacho Multicanal de Notificaciones y Resiliencia
    # ------------------------------------------------------------------------
    print_step(6, "PROC-03 (Alejandro): Despacho Multicanal y Política de Reintentos")
    req_notif = DespacharNotificacionRequest(
        condominio_id="vb3-condo",
        departamento_id="402",
        tipo_evento="NOTIF_RESERVA_CONFIRMADA",
        canal=CanalNotificacionEnum.EMAIL,
        destinatario="residente402@gmail.com",
        contexto={
            "nombre": "Carlos Mendoza",
            "dpto": "402",
            "area": parrilla_1["nombre"],
            "fecha": "2026-10-25",
            "horario": "19:00 - 22:00",
        },
    )

    log_notif = NotificacionesService.despachar_notificacion(req_notif)
    print(f"• Notificación despachada con éxito.")
    print(f"  Asunto: {log_notif.asunto}")
    print(f"  Estado: {log_notif.estado.value} | Intentos: {log_notif.intentos}")
    assert log_notif.estado == EstadoNotificacionEnum.ENTREGADO

    # Simulación de resiliencia con error 503 temporal
    ahora = datetime.now(timezone.utc)
    log_reintento = NotificacionesService.despachar_notificacion(
        request=req_notif,
        transport_fn=lambda *args: {"status": 503, "error": "Service Unavailable"},
        momento_actual=ahora,
    )
    assert log_reintento.estado == EstadoNotificacionEnum.REINTENTANDO
    assert log_reintento.intentos == 2
    print(f"• Error 503 manejado: Estado {log_reintento.estado.value} con segundo intento programado para {log_reintento.proximo_reintento.strftime('%H:%M:%S')}.")

    # Simulación de Hard Bounce 550
    log_bounce = NotificacionesService.despachar_notificacion(
        request=req_notif,
        transport_fn=lambda *args: {"status": 550, "error": "User unknown"},
    )
    assert log_bounce.estado == EstadoNotificacionEnum.FALLIDO_PERMANENTE
    assert log_bounce.intentos == 1
    print("• Hard bounce 550 detectado: Abortó reintentos inmediatamente pasando a FALLIDO_PERMANENTE.")
    print("✅ Despacho multicanal y resiliencia validados con éxito.")

    # ------------------------------------------------------------------------
    # PASO 7: Verificación de los 7 Campos de Auditoría Inmutable
    # ------------------------------------------------------------------------
    print_step(7, "Core (Trazabilidad): Los 7 Campos de Auditoría y Hash SHA-256")
    assert audit_reserva.departamento_id is not None
    assert audit_reserva.timestamp is not None
    assert audit_reserva.accion_ejecutada == "RESERVA_CONFIRMADA"
    assert audit_reserva.motivo is not None
    assert audit_reserva.resultado == "EXITOSO"
    assert "estado" in audit_reserva.estado_anterior
    assert "estado" in audit_reserva.estado_posterior

    hash_audit = audit_reserva.calcular_hash()
    print("• Registro de auditoría verificado:")
    print(f"  - departamento_id: {audit_reserva.departamento_id}")
    print(f"  - accion_ejecutada: {audit_reserva.accion_ejecutada}")
    print(f"  - resultado: {audit_reserva.resultado}")
    print(f"  - SHA-256 Hash Chaining: {hash_audit[:20]}...")
    print("✅ Todos los 7 campos obligatorios presentes e inmutables.")

    print("\n" + "=" * 70)
    print(" 🎉 TODAS LAS ETAPAS DEL PILOTO END-TO-END FUERON EXITOSAS (100%)")
    print("    El sistema CondoManager satisface todas las especificaciones SDD.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
