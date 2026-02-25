"use client";

import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";

function ActivateContent() {
  const searchParams = useSearchParams();
  const userCode = searchParams.get("user_code");
  const client = searchParams.get("client");

  const [manualCode, setManualCode] = useState("");
  const [showTroubleshoot, setShowTroubleshoot] = useState(false);
  const [copied, setCopied] = useState(false);

  const AUTH0_DOMAIN = process.env.NEXT_PUBLIC_AUTH0_ISSUER || "https://auth.navralabs.com";
  const activateUrl = `${AUTH0_DOMAIN}/activate`;

  const handleContinue = () => {
    const code = userCode || manualCode;
    if (code) {
      window.location.href = `${activateUrl}?user_code=${code}`;
    } else {
      window.location.href = activateUrl;
    }
  };

  const copyCode = () => {
    if (userCode) {
      navigator.clipboard.writeText(userCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const isVSCode = client === "vscode" || client === "vs-code";

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-[#0B1324] via-[#070B12] to-[#070B12]">
      {/* Ambient glow effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[15%] left-[20%] w-[1200px] h-[800px] bg-[#4AA8FF]/20 rounded-full blur-[128px]" />
        <div className="absolute bottom-[30%] right-[15%] w-[1000px] h-[700px] bg-[#6366F1]/16 rounded-full blur-[128px]" />
      </div>

      <div className="relative w-full max-w-4xl">
        <div className="grid md:grid-cols-2 gap-6">
          {/* Brand Section */}
          <div className="relative border border-white/[0.18] rounded-[22px] bg-[#020617]/35 backdrop-blur-sm p-6 shadow-2xl overflow-hidden">
            {/* Gradient overlay */}
            <div className="absolute inset-[-2px] bg-gradient-to-br from-[#4AA8FF]/22 via-transparent to-[#6366F1]/16 pointer-events-none rounded-[22px]" />

            <div className="relative z-10">
              {/* Logo */}
              <div className="flex items-center gap-3 mb-4">
                <div className="w-10 h-10 rounded-[14px] bg-gradient-to-br from-[#7CC4FF] via-[#4AA8FF] to-[#6366F1]/55 shadow-[0_10px_30px_rgba(74,168,255,0.25)]" />
                <span className="text-xl font-bold tracking-wide text-white">NAVI</span>
              </div>

              {/* Heading */}
              <h1 className="text-[28px] font-semibold mb-2 text-white/95 tracking-tight">
                Connect your workspace
              </h1>
              <p className="text-white/70 leading-relaxed mb-6">
                Secure sign-in happens in your browser. Credentials never enter {isVSCode ? "VS Code" : "your application"}.
              </p>

              {/* Feature bullets */}
              <div className="space-y-3">
                <div className="flex gap-3 items-start">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#4AA8FF] shadow-[0_0_0_4px_rgba(74,168,255,0.10)] mt-1.5 flex-shrink-0" />
                  <p className="text-sm text-white/80 leading-relaxed">
                    Enterprise-grade authentication with Auth0 + custom domain.
                  </p>
                </div>
                <div className="flex gap-3 items-start">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#4AA8FF] shadow-[0_0_0_4px_rgba(74,168,255,0.10)] mt-1.5 flex-shrink-0" />
                  <p className="text-sm text-white/80 leading-relaxed">
                    Device authorization designed for desktop + CLI clients.
                  </p>
                </div>
                <div className="flex gap-3 items-start">
                  <div className="w-2.5 h-2.5 rounded-full bg-[#4AA8FF] shadow-[0_0_0_4px_rgba(74,168,255,0.10)] mt-1.5 flex-shrink-0" />
                  <p className="text-sm text-white/80 leading-relaxed">
                    After approval, NAVI returns you to {isVSCode ? "VS Code" : "your application"} automatically.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Auth Panel */}
          <div className="border border-white/[0.18] rounded-[22px] bg-[#101736]/72 backdrop-blur-xl p-6 shadow-2xl">
            <h2 className="text-base font-semibold mb-1.5 text-white/95">Sign in</h2>
            <p className="text-xs text-white/70 mb-6 leading-relaxed">
              {isVSCode
                ? "Continue in your browser to connect NAVI to VS Code."
                : "Use your organization account to continue."}
            </p>

            {/* Main CTA */}
            <button
              onClick={handleContinue}
              className="w-full h-11 rounded-xl bg-gradient-to-r from-[#4AA8FF] to-[#6366F1]/85
                         border border-[#7CC4FF]/32 font-semibold text-white
                         hover:brightness-110 transition-all duration-200 shadow-lg
                         hover:shadow-[#4AA8FF]/25 hover:shadow-xl"
            >
              Continue in browser
            </button>

            {/* Security messaging */}
            <p className="mt-3 text-xs text-white/50 text-center leading-relaxed">
              Credentials never enter VS Code. Authentication happens securely in your browser.
            </p>

            {/* Troubleshooting section - Code only visible here */}
            <div className="mt-6 pt-4 border-t border-white/[0.08]">
              <button
                onClick={() => setShowTroubleshoot(!showTroubleshoot)}
                className="text-xs text-white/60 hover:text-white/90 transition-colors flex items-center gap-1.5"
              >
                <span className={`transform transition-transform ${showTroubleshoot ? "rotate-90" : ""}`}>▸</span>
                Having trouble?
              </button>

              {showTroubleshoot && (
                <div className="mt-3 space-y-3">
                  {userCode && (
                    <div>
                      <label className="block text-xs text-white/60 mb-1.5">
                        Your device code:
                      </label>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-sm px-3 py-1.5 rounded-lg bg-white/[0.08] border border-white/[0.12] text-[#7CC4FF] flex-1">
                          {userCode}
                        </span>
                        <button
                          onClick={copyCode}
                          className="px-3 py-1.5 rounded-lg bg-white/[0.06] hover:bg-white/[0.1]
                                     border border-white/[0.12] text-xs font-medium text-white/90
                                     transition-colors"
                        >
                          {copied ? "✓ Copied" : "Copy"}
                        </button>
                      </div>
                    </div>
                  )}

                  {!userCode && (
                    <div>
                      <label className="block text-xs text-white/60 mb-1.5">
                        Enter your device code from VS Code:
                      </label>
                      <input
                        type="text"
                        value={manualCode}
                        onChange={(e) => setManualCode(e.target.value.toUpperCase())}
                        placeholder="XXXX-XXXX"
                        className="w-full px-3 py-2 rounded-lg bg-[#020617]/28 border border-white/[0.15]
                                   text-white font-mono text-sm focus:outline-none focus:border-[#4AA8FF]/50
                                   focus:ring-1 focus:ring-[#4AA8FF]/30"
                      />
                    </div>
                  )}

                  <p className="text-xs text-white/60 leading-relaxed">
                    If your browser didn't open automatically, you can manually visit{" "}
                    <a
                      href={activateUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-[#7CC4FF] hover:underline"
                    >
                      {activateUrl}
                    </a>
                  </p>
                </div>
              )}
            </div>

            {isVSCode && (
              <p className="mt-6 text-xs text-white/50 text-center leading-relaxed">
                After approval, you'll be redirected back to VS Code automatically.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ActivatePage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0B1324] via-[#070B12] to-[#070B12]">
        <div className="text-white">Loading...</div>
      </div>
    }>
      <ActivateContent />
    </Suspense>
  );
}
