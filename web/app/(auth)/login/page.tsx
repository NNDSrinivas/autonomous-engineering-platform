import React from "react";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getSession } from "@auth0/nextjs-auth0";
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

export default async function LoginPage() {
  // Redirect to home if already logged in
  const session = await getSession();
  if (session?.user) {
    redirect("/");
  }

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
