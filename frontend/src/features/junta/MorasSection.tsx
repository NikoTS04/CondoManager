import { Clock3 } from "lucide-react";
import { Alert } from "@/components/ui/Alert";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";

interface MorasSectionProps {
  isAuditor: boolean;
  feedback: string | null;
  onEvaluate: () => void;
}

export function MorasSection({ isAuditor, feedback, onEvaluate }: MorasSectionProps) {
  return (
    <Card>
      <CardHeader
        title="Control de moras"
        description="Consulta las reglas de gracia, postergación de comprobantes y solvencia."
        actions={!isAuditor ? (
          <Button
            onClick={onEvaluate}
            icon={<Clock3 className="h-4 w-4" aria-hidden="true" />}
          >
            Evaluar moras
          </Button>
        ) : undefined}
      />
      <CardBody className="space-y-4">
        {isAuditor && (
          <div className="rounded-lg border border-audit-200 bg-audit-50 p-3">
            <Badge tone="audit">Solo lectura</Badge>
          </div>
        )}
        {feedback && (
          <Alert tone="info" title="Simulación del motor de moras">
            {feedback}
          </Alert>
        )}
        <div className="rounded-lg border border-line bg-canvas p-4">
          <h3 className="font-semibold">Reglas de cálculo</h3>
          <ul className="mt-2 list-inside list-disc space-y-2 text-sm text-muted">
            <li>Se respetan dos días de gracia después de la fecha de vencimiento.</li>
            <li>Un comprobante en revisión puede postergar la evaluación de mora.</li>
            <li>La mora activa puede afectar la solvencia y el acceso a reservas.</li>
          </ul>
        </div>
      </CardBody>
    </Card>
  );
}
