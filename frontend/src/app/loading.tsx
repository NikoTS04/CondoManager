import { Spinner } from "@/components/ui/Feedback";

export default function Loading() {
  return (
    <div className="flex min-h-64 items-center justify-center">
      <Spinner label="Cargando página…" />
    </div>
  );
}
