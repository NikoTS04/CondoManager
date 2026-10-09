"use client";

import React from "react";
import { useAuth, UserRole } from "@/context/AuthContext";
import AccessDenied from "@/components/layout/AccessDenied";
import { Spinner } from "@/components/ui/Feedback";

interface RoleGuardProps {
  allowedRoles: UserRole[];
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export default function RoleGuard({ allowedRoles, fallback, children }: RoleGuardProps) {
  const { user, authReady } = useAuth();

  if (!authReady) {
    return (
      <div className="flex min-h-64 items-center justify-center">
        <Spinner label="Verificando tu sesión…" />
      </div>
    );
  }

  if (!user || !allowedRoles.includes(user.rol)) {
    return <>{fallback ?? <AccessDenied />}</>;
  }

  return <>{children}</>;
}
