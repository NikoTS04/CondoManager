"use client";

import React from "react";
import { useAuth, UserRole } from "@/context/AuthContext";

interface RoleGuardProps {
  allowedRoles: UserRole[];
  fallback?: React.ReactNode;
  children: React.ReactNode;
}

export default function RoleGuard({ allowedRoles, fallback = null, children }: RoleGuardProps) {
  const { user } = useAuth();

  if (!user || !allowedRoles.includes(user.rol)) {
    return <>{fallback}</>;
  }

  return <>{children}</>;
}
