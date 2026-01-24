"use client";

import { useUser } from "@auth0/nextjs-auth0/client";

export interface AuthUser {
  sub: string;
  email: string;
  name: string;
  picture?: string;
  roles: string[];
  org: string;
}

export function useAuth() {
  const { user, isLoading, error } = useUser();

  const authUser: AuthUser | null = user
    ? {
        sub: user.sub as string,
        email: user.email as string,
        name: user.name as string,
        picture: user.picture as string | undefined,
        roles: (user["https://navralabs.com/roles"] as string[]) || ["viewer"],
        org: (user["https://navralabs.com/org"] as string) || "public",
      }
    : null;

  return {
    user: authUser,
    isLoading,
    error,
    isAuthenticated: !!user,
  };
}

export function useProtectedRoute(options?: {
  requiredRoles?: string[];
}) {
  const { user, isLoading, isAuthenticated } = useAuth();

  // Check role-based access
  const hasRequiredRole =
    !options?.requiredRoles ||
    (user?.roles &&
      options.requiredRoles.some((role) => user.roles.includes(role)));

  return {
    user,
    isLoading,
    isAuthenticated,
    hasRequiredRole,
    isAuthorized: isAuthenticated && hasRequiredRole,
  };
}
