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
  const [copiedCode, setCopiedCode] = useState(false);
  const [showTroubleshoot, setShowTroubleshoot] = useState(false);

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
            Continue in browser
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

            {signInStatus.userCode && (
              <div className="premium-auth-entry__troubleshoot">
                <button
                  type="button"
                  className="premium-auth-entry__troubleshoot-toggle"
                  onClick={() => setShowTroubleshoot(!showTroubleshoot)}
                >
                  <span className={`toggle-icon ${showTroubleshoot ? "open" : ""}`}>▸</span>
                  Having trouble?
                </button>

                {showTroubleshoot && (
                  <div className="premium-auth-entry__status-helper">
                    <span className="helper-label">Your device code:</span>
                    <div className="premium-auth-entry__status-code">
                      <span className="code-pill">Code: {signInStatus.userCode}</span>
                      <button type="button" onClick={() => copyCode(signInStatus.userCode || "")}>
                        {copiedCode ? "✓ Copied" : "Copy"}
                      </button>
                    </div>
                    {signInStatus.verificationUri && (
                      <button
                        type="button"
                        className="premium-auth-entry__status-link"
                        onClick={() => openExternal(signInStatus.verificationUri || "")}
                      >
                        Open sign-in page manually
                      </button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default PremiumAuthEntry;
