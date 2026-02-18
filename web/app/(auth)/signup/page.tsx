import React from "react";
import { redirect } from "next/navigation";
import { getSession } from "@auth0/nextjs-auth0";
import { PremiumSignupShell } from "@/components/auth/PremiumSignupShell";

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

  return <PremiumSignupShell />;
}
