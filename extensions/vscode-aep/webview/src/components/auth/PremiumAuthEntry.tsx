import React, { useState } from "react";
import naviLogo from "../../assets/navi-logo.svg";
import "./PremiumAuthEntry.css";

type EntryMode = "signin" | "signup";

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
  subtitle = "Use secure device authorization for sign in. Sign up opens NAVI in your browser.",
  variant = "default",
  onSignIn,
  onSignUp,
  signInStatus,
}: PremiumAuthEntryProps) {
  const [mode, setMode] = useState<EntryMode>("signin");
  const [logoFailed, setLogoFailed] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);

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

  const openExternal = (url: string) => {
    if (!url) return;
    if (typeof window !== "undefined" && window.parent && window.parent !== window) {
      window.parent.postMessage({ type: "openExternal", url }, "*");
      return;
    }
    window.open(url, "_blank", "noopener,noreferrer");
  };

  const copyCode = async (code: string) => {
    if (!code || typeof navigator === "undefined" || !navigator.clipboard) return;
    try {
      await navigator.clipboard.writeText(code);
      setCopiedCode(true);
      window.setTimeout(() => setCopiedCode(false), 1500);
    } catch {
      setCopiedCode(false);
    }
  };

  const isSignInMode = mode === "signin";
  const showStatus = isSignInMode && signInStatus && signInStatus.message;
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
            {mode === "signin" ? "Continue to Sign in" : "Create account on web"}
          </button>
          <button
            type="button"
            className="premium-auth-entry__btn secondary"
            onClick={handleSecondary}
          >
            {mode === "signin" ? "Need an account?" : "Already have one?"}
          </button>
        </div>
        <p className="premium-auth-entry__mode-note">
          {isSignInMode
            ? "Sign in uses secure browser authorization and returns to VS Code automatically."
            : "Sign up opens navralabs.com/signup in your external browser."}
        </p>

        {showStatus && (
          <div className={`premium-auth-entry__status ${statusClass}`}>
            <p>{signInStatus.message}</p>
            {signInStatus.userCode && (
              <div className="premium-auth-entry__status-code">
                <span>Code: {signInStatus.userCode}</span>
                <button type="button" onClick={() => copyCode(signInStatus.userCode || "")}>
                  {copiedCode ? "Copied" : "Copy"}
                </button>
              </div>
            )}
            {signInStatus.recoverable && signInStatus.verificationUri && (
              <button
                type="button"
                className="premium-auth-entry__status-link"
                onClick={() => openExternal(signInStatus.verificationUri || "")}
              >
                Open authorization page
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default PremiumAuthEntry;
