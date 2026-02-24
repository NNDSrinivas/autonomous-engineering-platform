import React from "react";
import Link from "next/link";
import {
  AuthCard,
  AuthHeader,
  AuthFooter,
  AuthDivider,
} from "@/components/auth/AuthCard";
import { LoginForm } from "@/components/auth/LoginForm";
import { SocialLoginButtons } from "@/components/auth/SocialLoginButtons";
import { SSOLoginButton } from "@/components/auth/SSOLoginButton";

export const metadata = {
  title: "Sign In | NAVI",
  description: "Sign in to your NAVI account",
};

export default function LoginPage() {
  return (
    <AuthCard>
      <AuthHeader
        title="Welcome back"
        subtitle="Sign in to your NAVI account"
      />

      {/* Social login buttons */}
      <SocialLoginButtons mode="login" />

      <AuthDivider text="or continue with email" />

      {/* Email/password form */}
      <LoginForm />

      {/* SSO option */}
      <SSOLoginButton />

      <AuthFooter>
        Don&apos;t have an account?{" "}
        <Link href="/signup" className="text-primary hover:underline font-medium">
          Sign up
        </Link>
      </AuthFooter>
    </AuthCard>
  );
}
