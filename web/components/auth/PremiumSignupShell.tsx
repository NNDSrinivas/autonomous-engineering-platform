"use client";

import Link from "next/link";
import { useState } from "react";
import { Sparkles, ShieldCheck, Zap, Bot } from "lucide-react";
import { SignupForm } from "@/components/auth/SignupForm";
import { SocialLoginButtons } from "@/components/auth/SocialLoginButtons";
import { AuthDivider } from "@/components/auth/AuthCard";
import styles from "./premium-signup.module.css";

function BrandMark({ className }: { className?: string }) {
  const [logoFailed, setLogoFailed] = useState(false);

  return (
    <div className={`${styles.brand} ${className || ""}`}>
      <div className={styles.logoOrb}>
        {!logoFailed ? (
          <img
            src="/navi-logo.svg"
            alt="NAVI logo"
            className={styles.logoImage}
            onError={() => setLogoFailed(true)}
          />
        ) : (
          <div className={styles.logoFallback}>N</div>
        )}
        <span className={styles.currentPulse} />
      </div>
      <span className={styles.brandWordmark}>NAVI</span>
    </div>
  );
}

export function PremiumSignupShell() {
  return (
    <div className={styles.shell}>
      <div className={styles.backdrop} aria-hidden="true" />
      <div className={styles.mesh} aria-hidden="true" />
      <div className={styles.grid} aria-hidden="true" />

      <section className={styles.hero}>
        <BrandMark />

        <p className={styles.eyebrow}>Agentic Engineering Platform</p>
        <h1 className={styles.heroTitle}>
          Build faster with an AI teammate that ships production code.
        </h1>
        <p className={styles.heroSubtitle}>
          From codebase context to PR-ready output. NAVI helps teams move with
          confidence, clarity, and control.
        </p>

        <div className={styles.statRow}>
          <div className={styles.statCard}>
            <Zap size={16} />
            <span>Faster execution</span>
          </div>
          <div className={styles.statCard}>
            <ShieldCheck size={16} />
            <span>Governed workflows</span>
          </div>
          <div className={styles.statCard}>
            <Bot size={16} />
            <span>Context-aware AI</span>
          </div>
        </div>
      </section>

      <section className={styles.formPanel}>
        <div className={styles.formCard}>
          <BrandMark className={styles.formBrand} />

          <div className={styles.formHeading}>
            <h2>Create your NAVI account</h2>
            <p>Start free. Upgrade when your team is ready.</p>
          </div>

          <SocialLoginButtons mode="signup" />
          <AuthDivider text="or sign up with email" />
          <SignupForm />

          <p className={styles.signInPrompt}>
            Already have an account?{" "}
            <Link href="/login" className={styles.signInLink}>
              Sign in
            </Link>
          </p>

          <p className={styles.finePrint}>
            <Sparkles size={14} />
            Secure signup powered by NAVI identity.
          </p>
        </div>
      </section>
    </div>
  );
}
