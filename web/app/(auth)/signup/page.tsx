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
import { SignupForm } from "@/components/auth/SignupForm";
import { SocialLoginButtons } from "@/components/auth/SocialLoginButtons";

export const metadata = {
  title: "Sign Up | NAVI",
  description: "Create your NAVI account",
};

export default async function SignupPage() {
  // Redirect to home if already logged in
  const session = await getSession();
  if (session?.user) {
    redirect("/");
  }

  return (
    <AuthCard>
      <AuthHeader
        title="Create your account"
        subtitle="Start building with NAVI"
      />

      {/* Social signup buttons */}
      <SocialLoginButtons mode="signup" />

      <AuthDivider text="or sign up with email" />

      {/* Registration form */}
      <SignupForm />

      <AuthFooter>
        Already have an account?{" "}
        <Link href="/login" className="text-primary hover:underline font-medium">
          Sign in
        </Link>
      </AuthFooter>
    </AuthCard>
  );
}
