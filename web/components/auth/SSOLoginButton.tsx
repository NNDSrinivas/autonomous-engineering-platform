"use client";

import React, { useState } from "react";
import { Building2, ChevronDown, ChevronUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function SSOLoginButton() {
  const [isExpanded, setIsExpanded] = useState(false);
  const [orgSlug, setOrgSlug] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleSSOLogin = async () => {
    if (!orgSlug.trim()) return;

    setIsLoading(true);
    // Redirect to Auth0 with the organization connection
    // The connection name follows the pattern: saml-{org} or oidc-{org}
    window.location.href = `/api/auth/login?connection=${orgSlug.toLowerCase()}&organization=${orgSlug.toLowerCase()}`;
  };

  return (
    <div className="mt-4">
      <Button
        type="button"
        variant="ghost"
        className="w-full text-muted-foreground hover:text-foreground"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <Building2 className="mr-2 h-4 w-4" />
        Sign in with SSO
        {isExpanded ? (
          <ChevronUp className="ml-2 h-4 w-4" />
        ) : (
          <ChevronDown className="ml-2 h-4 w-4" />
        )}
      </Button>

      {isExpanded && (
        <div className="mt-3 space-y-3 rounded-lg border border-border bg-secondary/20 p-4">
          <div className="space-y-2">
            <Label htmlFor="org-slug" className="text-sm">
              Organization
            </Label>
            <Input
              id="org-slug"
              placeholder="Enter your organization name"
              value={orgSlug}
              onChange={(e) => setOrgSlug(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSSOLogin()}
            />
          </div>
          <Button
            type="button"
            className="w-full"
            onClick={handleSSOLogin}
            disabled={!orgSlug.trim() || isLoading}
          >
            {isLoading ? "Connecting..." : "Continue with SSO"}
          </Button>
        </div>
      )}
    </div>
  );
}
