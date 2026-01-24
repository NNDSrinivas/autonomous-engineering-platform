import React from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getSession } from "@auth0/nextjs-auth0";
import { User, Settings, LogOut } from "lucide-react";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getSession();

  if (!session?.user) {
    redirect("/login");
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2">
            <div className="h-8 w-8 rounded-lg gradient-ai flex items-center justify-center">
              <span className="text-lg font-bold text-white">N</span>
            </div>
            <span className="text-xl font-bold gradient-ai-text">NAVI</span>
          </Link>

          {/* User menu */}
          <div className="flex items-center gap-4">
            <Link
              href="/profile"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              {session.user.picture ? (
                <img
                  src={session.user.picture}
                  alt={session.user.name || "User"}
                  className="h-8 w-8 rounded-full border border-border"
                />
              ) : (
                <div className="h-8 w-8 rounded-full bg-secondary flex items-center justify-center">
                  <User className="h-4 w-4" />
                </div>
              )}
              <span className="hidden sm:inline">{session.user.name}</span>
            </Link>

            <a
              href="/api/auth/logout"
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Sign Out</span>
            </a>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-8">{children}</main>
    </div>
  );
}
