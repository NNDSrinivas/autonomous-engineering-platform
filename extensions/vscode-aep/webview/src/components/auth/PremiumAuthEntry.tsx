import React, { useState } from "react";
import naviLogo from "../../assets/navi-logo.svg";
import "./PremiumAuthEntry.css";

interface PremiumSignInStatus {
  state: "starting" | "browser_opened" | "waiting_for_approval" | "success" | "error";
  message: string;
  userCode?: string;
  verificationUri?: string;
  recoverable?: boolean;
}

interface PremiumAuthEntryProps {
  title?: string;
  subtitle?: string;
  variant?: "default" | "compact";
  onSignIn: () => void;
  onSignUp: () => void;
  signInStatus?: PremiumSignInStatus | null;
}

export function PremiumAuthEntry({
  title = "Sign in to NAVI",
  subtitle = "Securely sign in using your browser. Credentials never enter VS Code.",
  variant = "default",
  onSignIn,
  onSignUp,
  signInStatus,
}: PremiumAuthEntryProps) {
  const [logoFailed, setLogoFailed] = useState(false);

  const showStatus = signInStatus && signInStatus.message;
  const statusClass = showStatus ? `is-${signInStatus.state}` : "";

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
        <div className="premium-auth-entry__actions">
          <button type="button" className="premium-auth-entry__btn primary" onClick={onSignIn}>
            Sign in
          </button>
          <button type="button" className="premium-auth-entry__btn secondary" onClick={onSignUp}>
            Sign up
          </button>
        </div>
        <p className="premium-auth-entry__mode-note">
          After approval, NAVI connects automatically and returns you here.
        </p>

        {showStatus && (
          <div className={`premium-auth-entry__status ${statusClass}`}>
            <p>{signInStatus.message}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default PremiumAuthEntry;
