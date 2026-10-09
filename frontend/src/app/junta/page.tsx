import JuntaPortal from "@/features/junta/JuntaPortal";
import RoleGuard from "@/components/RoleGuard";

export default function JuntaPage() {
  return (
    <RoleGuard allowedRoles={["ADMIN_JUNTA", "SUPERADMIN", "AUDITOR"]}>
      <JuntaPortal />
    </RoleGuard>
  );
}
