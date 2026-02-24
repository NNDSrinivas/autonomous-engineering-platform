"use client";

import { useEffect, useState, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { useUser } from "@auth0/nextjs-auth0/client";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, ShieldCheck, Monitor, CheckCircle2, XCircle, AlertTriangle } from "lucide-react";
import Link from "next/link";

type AuthStatus = "loading" | "checking" | "approving" | "success" | "error" | "input_required";

function DeviceAuthorizeContent() {
  const searchParams = useSearchParams();
  const { user, isLoading: authLoading } = useUser();
  const [userCode, setUserCode] = useState(searchParams.get("user_code") || "");
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // If user is not logged in, redirect to login with returnTo
    if (!authLoading && !user) {
      const currentUrl = window.location.pathname + window.location.search;
      window.location.href = `/api/auth/login?returnTo=${encodeURIComponent(currentUrl)}`;
      return;
    }

    // If user is logged in and user_code is in URL, auto-approve
    if (user && searchParams.get("user_code")) {
      handleApproval(searchParams.get("user_code")!);
    } else if (user) {
      setStatus("input_required");
    }
  }, [user, authLoading, searchParams]);

  const handleApproval = async (code: string) => {
    if (!code.trim()) {
      setError("Please enter the device code");
      return;
    }

    setStatus("approving");
    setError(null);

    try {
      const backendUrl = process.env.NEXT_PUBLIC_AEP_CORE || "http://localhost:8787";
      const response = await fetch(`${backendUrl}/oauth/device/authorize`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          user_code: code.trim().toUpperCase(),
          action: "approve",
          user_id: user?.sub,
          org_id: user?.["https://navralabs.com/org"] || "public",
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: "Authorization failed" }));
        throw new Error(errorData.detail || `HTTP ${response.status}`);
      }

      setStatus("success");
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Failed to authorize device");
    }
  };

  const handleFormSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    handleApproval(userCode);
  };

  if (authLoading || status === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary mb-4" />
          <p className="text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="max-w-md w-full p-8">
          <div className="text-center">
            <div className="mx-auto w-16 h-16 rounded-full bg-green-500/10 flex items-center justify-center mb-4">
              <CheckCircle2 className="h-8 w-8 text-green-500" />
            </div>
            <h1 className="text-2xl font-bold mb-2">Device Authorized</h1>
            <p className="text-muted-foreground mb-6">
              You can now return to your VS Code extension. The device has been successfully authorized.
            </p>
            <Button asChild variant="outline">
              <Link href="/app">Go to Dashboard</Link>
            </Button>
          </div>
        </Card>
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="max-w-md w-full p-8">
          <div className="text-center">
            <div className="mx-auto w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
              <XCircle className="h-8 w-8 text-destructive" />
            </div>
            <h1 className="text-2xl font-bold mb-2">Authorization Failed</h1>
            <p className="text-destructive mb-6">{error || "An unknown error occurred"}</p>
            <div className="space-y-3">
              <Button
                onClick={() => {
                  setStatus("input_required");
                  setError(null);
                }}
                variant="outline"
                className="w-full"
              >
                Try Again
              </Button>
              <Button asChild variant="ghost" className="w-full">
                <Link href="/app">Go to Dashboard</Link>
              </Button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="max-w-md w-full p-8">
        <div className="text-center mb-6">
          <div className="mx-auto w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mb-4">
            <ShieldCheck className="h-8 w-8 text-primary" />
          </div>
          <h1 className="text-2xl font-bold mb-2">Authorize Device</h1>
          <p className="text-muted-foreground">
            To continue, enter the device code shown in your VS Code extension.
          </p>
        </div>

        <form onSubmit={handleFormSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="userCode">Device Code</Label>
            <div className="relative">
              <Monitor className="absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
              <Input
                id="userCode"
                type="text"
                value={userCode}
                onChange={(e) => setUserCode(e.target.value.toUpperCase())}
                placeholder="XXXX-XXXX"
                className="pl-10 uppercase tracking-wider"
                maxLength={9}
                autoComplete="off"
                autoFocus
              />
            </div>
          </div>

          {error && (
            <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-sm text-destructive flex items-start gap-2">
              <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <Button
            type="submit"
            className="w-full"
            disabled={status === "approving" || !userCode.trim()}
          >
            {status === "approving" ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Authorizing...
              </>
            ) : (
              "Authorize Device"
            )}
          </Button>
        </form>

        <div className="mt-6 pt-6 border-t border-border">
          <p className="text-sm text-muted-foreground text-center">
            Signed in as <strong>{user?.email}</strong>
          </p>
          <div className="flex justify-center gap-4 mt-3">
            <Button asChild variant="ghost" size="sm">
              <Link href="/app">Dashboard</Link>
            </Button>
            <Button asChild variant="ghost" size="sm">
              <a href="/api/auth/logout">Sign Out</a>
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
}

export default function DeviceAuthorizePage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-background">
          <div className="text-center">
            <Loader2 className="h-8 w-8 animate-spin mx-auto text-primary mb-4" />
            <p className="text-muted-foreground">Loading...</p>
          </div>
        </div>
      }
    >
      <DeviceAuthorizeContent />
    </Suspense>
  );
}
