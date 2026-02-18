import React, { useState } from "react";
import naviLogo from "../../assets/navi-logo.svg";
import "./PremiumAuthEntry.css";

type EntryMode = "signin" | "signup";

interface PremiumAuthEntryProps {
  title?: string;
  subtitle?: string;
  variant?: "default" | "compact";
  onSignIn: () => void;
  onSignUp: () => void;
}

export function PremiumAuthEntry({
  title = "Sign in to NAVI",
  subtitle = "Unlock your personalized workspace, session memory, and team context.",
  variant = "default",
  onSignIn,
  onSignUp,
}: PremiumAuthEntryProps) {
  const [mode, setMode] = useState<EntryMode>("signup");
  const [logoFailed, setLogoFailed] = useState(false);

  const handlePrimary = () => {
    if (mode === "signin") {
      onSignIn();
      return;
    }
    onSignUp();
  };

  const handleSecondary = () => {
    if (mode === "signin") {
      onSignUp();
      return;
    }
    onSignIn();
  };

  return (
    <div className={`premium-auth-entry ${variant === "compact" ? "compact" : ""}`}>
      <div className="premium-auth-entry__hero">
        <div className="premium-auth-entry__brand">
          <div className="premium-auth-entry__logo-orb">
            {!logoFailed ? (
              <img
                src={naviLogo}
                alt="NAVI logo"
                className="premium-auth-entry__logo"
                onError={() => setLogoFailed(true)}
              />
            ) : (
              <div className="premium-auth-entry__fallback" aria-hidden="true">
                N
              </div>
            )}
            <span className="premium-auth-entry__current-pulse" aria-hidden="true" />
          </div>
          <span className="premium-auth-entry__wordmark">NAVI</span>
        </div>
        <h4 className="premium-auth-entry__title">{title}</h4>
        <p className="premium-auth-entry__subtitle">{subtitle}</p>
      </div>

      <div className="premium-auth-entry__controls">
        <div className="premium-auth-entry__switch" role="tablist" aria-label="Auth mode">
          <button
            type="button"
            role="tab"
            aria-selected={mode === "signin"}
            className={mode === "signin" ? "active" : ""}
            onClick={() => setMode("signin")}
          >
            Sign in
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={mode === "signup"}
            className={mode === "signup" ? "active" : ""}
            onClick={() => setMode("signup")}
          >
            Sign up
          </button>
        </div>

        <div className="premium-auth-entry__actions">
          <button type="button" className="premium-auth-entry__btn primary" onClick={handlePrimary}>
            {mode === "signin" ? "Continue to Sign in" : "Create account"}
          </button>
          <button
            type="button"
            className="premium-auth-entry__btn secondary"
            onClick={handleSecondary}
          >
            {mode === "signin" ? "Need an account?" : "Already have one?"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default PremiumAuthEntry;
