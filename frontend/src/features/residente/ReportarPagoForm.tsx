"use client";

import { useState } from "react";
import { CreditCard, Send } from "lucide-react";
import { Field, Input, Select } from "@/components/ui/Field";
import { MoneyInput } from "@/components/ui/MoneyInput";
import { FileDropzone } from "@/components/ui/FileDropzone";
import { ConfirmDialog } from "@/components/ui/Dialog";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader, CardBody } from "@/components/ui/Card";
import { Alert } from "@/components/ui/Alert";
import { MoneyAmount } from "@/components/domain/MoneyAmount";
import { isPositiveMoney } from "@/lib/money";
import { reportarPago, type ComprobantePago } from "@/lib/api";

function getTodayLima(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Lima",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

export interface ReportarPagoFormProps {
  departamentoId: string;
  onSuccess?: () => void;
  comprobantesExistentes?: ComprobantePago[];
}

export function ReportarPagoForm({
  departamentoId,
  onSuccess,
}: ReportarPagoFormProps) {
  const [banco, setBanco] = useState<string>("YAPE");
  const [numeroOperacion, setNumeroOperacion] = useState<string>("");
  const [montoPago, setMontoPago] = useState<string>("");
  const [fechaOperacion, setFechaOperacion] = useState<string>(getTodayLima());
  const [voucherFile, setVoucherFile] = useState<File | null>(null);

  const [confirmOpen, setConfirmOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Estados de retroalimentación
  const [alertState, setAlertState] = useState<{
    tone: "success" | "warning" | "danger" | "info";
    title: string;
    message: string;
    code?: string;
  } | null>(null);
  const [fieldErrors, setFieldErrors] = useState<{
    numeroOperacion?: string;
    monto?: string;
    fecha?: string;
    voucher?: string;
  }>({});

  function handleFormSubmit(e: React.FormEvent) {
    e.preventDefault();
    setAlertState(null);
    if (!departamentoId) return;
    const errors: typeof fieldErrors = {};

    const cleanOp = numeroOperacion.trim();
    if (!cleanOp) {
      errors.numeroOperacion = "Ingresa el número de operación bancaria.";
    }

    if (!isPositiveMoney(montoPago)) {
      errors.monto = "Ingresa un monto válido mayor a 0.";
    }

    if (!fechaOperacion) {
      errors.fecha = "Selecciona la fecha de la operación.";
    }
    if (!voucherFile) errors.voucher = "Adjunta el voucher de tu pago.";

    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    // La deduplicación autoritativa incluye fecha/monto y se hace en PostgreSQL.

    // Abre el diálogo de confirmación que repite el monto
    setConfirmOpen(true);
  }

  async function handleConfirmSubmit() {
    setIsSubmitting(true);
    setAlertState(null);

    try {
      if (!voucherFile) throw new Error("Adjunta el voucher de tu pago.");
      const res = await reportarPago({
        departamento_id: departamentoId,
        banco,
        numero_operacion: numeroOperacion.trim(),
        fecha_operacion: fechaOperacion,
        monto: montoPago,
        archivo_voucher: voucherFile,
      });

      setConfirmOpen(false);

      if (res.ok) {
        setAlertState({
          tone: res.duplicado ? "info" : "success",
          title: res.duplicado ? "Comprobante en evaluación" : "Comprobante recibido",
          message: res.duplicado
            ? "El comprobante ya estaba registrado. Conservamos el mismo reporte sin duplicarlo."
            : "Recibimos tu comprobante en revisión. El reporte no cancela la deuda hasta su aprobación.",
        });
        setNumeroOperacion("");
        setMontoPago("");
        setFechaOperacion(getTodayLima());
        setVoucherFile(null);
        if (onSuccess) onSuccess();
      } else {
        const err = res.errorCode || res.error || "";
        if (err.includes("VOUCHER_EN_EVALUACION")) {
          setAlertState({
            tone: "warning",
            title: "Comprobante en evaluación",
            message:
              "Este comprobante ya fue reportado y está en revisión por la junta directiva.",
            code: "VOUCHER_EN_EVALUACION",
          });
        } else if (err.includes("VOUCHER_YA_CONCILIADO")) {
          setAlertState({
            tone: "info",
            title: "Comprobante ya conciliado",
            message:
              "Este comprobante ya fue aprobado anteriormente. No necesitas reportarlo de nuevo.",
            code: "VOUCHER_YA_CONCILIADO",
          });
        } else {
          setAlertState({
            tone: "danger",
            title: "No pudimos registrar tu comprobante",
            message:
              res.error ||
              "Ocurrió un error inesperado al enviar el comprobante. Inténtalo de nuevo.",
          });
        }
      }
    } catch (error) {
      setConfirmOpen(false);
      setAlertState({ tone: "danger", title: "No pudimos enviar el comprobante", message: error instanceof Error ? error.message : "Comprueba la conexión e inténtalo de nuevo." });
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <>
      <Card>
        <CardHeader
          title="Reportar Comprobante"
          description="Registra tu transferencia o depósito para conciliar tus cuotas pendientes."
          icon={<CreditCard className="h-5 w-5 text-brand-600" aria-hidden />}
        />

        <CardBody className="space-y-4">
          {alertState && (
            <Alert
              tone={alertState.tone}
              title={alertState.title}
              code={alertState.code}
              onDismiss={() => setAlertState(null)}
            >
              {alertState.message}
            </Alert>
          )}

          <form onSubmit={handleFormSubmit} className="space-y-4">
            <Field label="Canal o Banco de Pago" required>
              <Select value={banco} onChange={(e) => setBanco(e.target.value)}>
                <option value="YAPE">Yape</option>
                <option value="PLIN">Plin</option>
                <option value="BCP">BCP Transferencia / Depósito</option>
                <option value="INTERBANK">Interbank</option>
                <option value="BBVA">BBVA</option>
                <option value="SCOTIABANK">Scotiabank</option>
              </Select>
            </Field>

            <Field
              label="Número de Operación Bancaria"
              required
              hint="La operación, fecha e importe permiten detectar reportes duplicados."
              error={fieldErrors.numeroOperacion}
            >
              <Input
                type="text"
                placeholder="Ej. 0089214"
                minLength={1}
                maxLength={50}
                value={numeroOperacion}
                onChange={(e) => {
                  setNumeroOperacion(e.target.value);
                  if (fieldErrors.numeroOperacion) {
                    setFieldErrors((prev) => ({
                      ...prev,
                      numeroOperacion: undefined,
                    }));
                  }
                }}
              />
            </Field>

            <div className="grid gap-4 sm:grid-cols-2">
              <Field
                label="Monto Pagado"
                required
                hint="Monto exacto transferido"
                error={fieldErrors.monto}
              >
                <MoneyInput
                  value={montoPago}
                  placeholder="0.00"
                  onValueChange={(val) => {
                    setMontoPago(val);
                    if (fieldErrors.monto) {
                      setFieldErrors((prev) => ({ ...prev, monto: undefined }));
                    }
                  }}
                  moneda="PEN"
                />
              </Field>

              <Field
                label="Fecha de Operación"
                required
                error={fieldErrors.fecha}
              >
                <Input
                  type="date"
                  value={fechaOperacion}
                  onChange={(e) => {
                    setFechaOperacion(e.target.value);
                    if (fieldErrors.fecha) {
                      setFieldErrors((prev) => ({ ...prev, fecha: undefined }));
                    }
                  }}
                />
              </Field>
            </div>

            <FileDropzone
              label="Comprobante de Pago (Voucher)"
              required
              file={voucherFile}
              error={fieldErrors.voucher}
              onFileChange={setVoucherFile}
              maxSizeMb={5}
            />

            <Button
              type="submit"
              variant="primary"
              fullWidth
              icon={<Send className="h-4 w-4" aria-hidden />}
            >
              Reportar Pago
            </Button>
          </form>
        </CardBody>
      </Card>

      {/* Diálogo de Confirmación que repite el monto antes de enviar */}
      <ConfirmDialog
        open={confirmOpen}
        title="Confirmar reporte de pago"
        confirmLabel="Confirmar y enviar"
        loading={isSubmitting}
        onConfirm={handleConfirmSubmit}
        onCancel={() => setConfirmOpen(false)}
      >
        <p>
          Estás por reportar un comprobante de pago por{" "}
          <strong className="text-brand-700">
            <MoneyAmount value={montoPago || "0.00"} moneda="PEN" />
          </strong>{" "}
          para la <strong>unidad seleccionada</strong> en{" "}
          <strong>{banco}</strong> con el número de operación{" "}
          <strong className="tabular-nums">{numeroOperacion}</strong>.
        </p>
        <p className="text-xs text-muted mt-2">
          La junta directiva revisará el voucher y conciliará tus cuotas. ¿Deseas continuar?
        </p>
      </ConfirmDialog>
    </>
  );
}
