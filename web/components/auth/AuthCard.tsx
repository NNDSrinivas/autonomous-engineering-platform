"use client";

import React from "react";
import Link from "next/link";
import { cn } from "@/lib/utils";

interface AuthCardProps {
  children: React.ReactNode;
  className?: string;
}

export function AuthCard({ children, className }: AuthCardProps) {
  return (
    <div
      className={cn(
        "w-full max-w-md rounded-xl border border-border bg-card p-8 shadow-lg",
        className
      )}
    >
      {children}
    </div>
  );
}

interface AuthHeaderProps {
  title: string;
  subtitle?: string;
}

export function AuthHeader({ title, subtitle }: AuthHeaderProps) {
  return (
    <div className="mb-8 text-center">
      {/* NAVI Logo */}
      <Link href="/" className="inline-block mb-6">
        <div className="flex items-center justify-center gap-2">
          <div className="h-10 w-10 rounded-lg gradient-ai flex items-center justify-center">
            <span className="text-xl font-bold text-white">N</span>
          </div>
          <span className="text-2xl font-bold gradient-ai-text">NAVI</span>
        </div>
      </Link>
      <h1 className="text-2xl font-semibold text-foreground">{title}</h1>
      {subtitle && (
        <p className="mt-2 text-sm text-muted-foreground">{subtitle}</p>
      )}
    </div>
  );
}

interface AuthFooterProps {
  children: React.ReactNode;
}

export function AuthFooter({ children }: AuthFooterProps) {
  return (
    <p className="mt-6 text-center text-sm text-muted-foreground">{children}</p>
  );
}

interface AuthDividerProps {
  text?: string;
}

export function AuthDivider({ text = "or" }: AuthDividerProps) {
  return (
    <div className="relative my-6">
      <div className="absolute inset-0 flex items-center">
        <div className="w-full border-t border-border" />
      </div>
      <div className="relative flex justify-center text-xs uppercase">
        <span className="bg-card px-2 text-muted-foreground">{text}</span>
      </div>
    </div>
  );
}
