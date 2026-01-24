import React from "react";
import Link from "next/link";
import { Mail, ArrowLeft } from "lucide-react";
import { AuthCard, AuthHeader } from "@/components/auth/AuthCard";
import { Button } from "@/components/ui/button";

export const metadata = {
  title: "Verify Email | NAVI",
  description: "Please verify your email address",
};

export default function VerifyEmailPage() {
  return (
    <AuthCard>
      <AuthHeader
        title="Check your email"
        subtitle="We've sent you a verification link"
      />

      <div className="flex justify-center mb-6">
        <div className="h-16 w-16 rounded-full gradient-ai flex items-center justify-center animate-glow-pulse">
          <Mail className="h-8 w-8 text-white" />
        </div>
      </div>

      <div className="text-center space-y-4">
        <p className="text-muted-foreground">
          We&apos;ve sent a verification email to your inbox. Click the link in
          the email to verify your account and complete the signup process.
        </p>

        <div className="rounded-lg border border-border bg-secondary/20 p-4 text-sm text-muted-foreground">
          <p className="font-medium text-foreground mb-2">
            Didn&apos;t receive the email?
          </p>
          <ul className="list-disc list-inside space-y-1 text-left">
            <li>Check your spam or junk folder</li>
            <li>Make sure you entered the correct email</li>
            <li>Wait a few minutes and check again</li>
          </ul>
        </div>

        <Button variant="outline" className="w-full" asChild>
          <Link href="/login">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Sign In
          </Link>
        </Button>
      </div>
    </AuthCard>
  );
}
