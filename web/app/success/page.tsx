"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

function SuccessContent() {
  const searchParams = useSearchParams();
  const client = searchParams.get("client");
  const [autoCloseCountdown, setAutoCloseCountdown] = useState(5);

  const isVSCode = client === "vscode" || client === "vs-code";

  useEffect(() => {
    // Try to auto-close (only works if window was opened by script)
    const timer = setInterval(() => {
      setAutoCloseCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(timer);
          window.close(); // Will only work if opened by window.open()
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, []);

  const handleClose = () => {
    window.close();
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-[#0B1324] via-[#070B12] to-[#070B12]">
      {/* Ambient glow effects */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[15%] left-[20%] w-[1200px] h-[800px] bg-[#4AA8FF]/20 rounded-full blur-[128px]" />
        <div className="absolute bottom-[30%] right-[15%] w-[1000px] h-[700px] bg-[#6366F1]/16 rounded-full blur-[128px]" />
      </div>

      <div className="relative w-full max-w-lg">
        <div className="border border-white/[0.18] rounded-[22px] bg-[#101736]/72 backdrop-blur-xl p-8 shadow-2xl text-center">
          {/* Success checkmark animation */}
          <div className="mb-6 flex justify-center">
            <div className="relative">
              <div className="w-20 h-20 rounded-full bg-gradient-to-br from-[#4AA8FF] to-[#6366F1]
                              flex items-center justify-center shadow-[0_20px_50px_rgba(74,168,255,0.4)]
                              animate-pulse">
                <svg
                  className="w-10 h-10 text-white"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={3}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>
              {/* Glow ring */}
              <div className="absolute inset-0 rounded-full bg-[#4AA8FF]/20 blur-xl animate-pulse" />
            </div>
          </div>

          {/* Success message */}
          <h1 className="text-2xl font-bold mb-2 text-white/95">
            NAVI is now connected{isVSCode ? " to VS Code" : ""}
          </h1>
          <p className="text-white/70 mb-8 leading-relaxed">
            {isVSCode
              ? "You can safely return to your workspace. Your session is active and secure."
              : "Authentication successful. Your session is now active."}
          </p>

          {/* Return to VS Code button */}
          {isVSCode && (
            <button
              onClick={handleClose}
              className="w-full h-11 rounded-xl bg-gradient-to-r from-[#4AA8FF] to-[#6366F1]/85
                         border border-[#7CC4FF]/32 font-semibold text-white
                         hover:brightness-110 transition-all duration-200 shadow-lg
                         hover:shadow-[#4AA8FF]/25 hover:shadow-xl mb-4"
            >
              Return to VS Code
            </button>
          )}

          {/* Close tab hint */}
          <p className="text-xs text-white/50 leading-relaxed">
            {autoCloseCountdown > 0 ? (
              <>This tab will close automatically in {autoCloseCountdown} seconds</>
            ) : (
              <>You can safely close this tab</>
            )}
          </p>

          {/* Manual close button (fallback) */}
          {!isVSCode && (
            <button
              onClick={handleClose}
              className="mt-4 px-4 py-2 rounded-lg bg-white/[0.06] hover:bg-white/[0.1]
                         border border-white/[0.12] text-sm font-medium text-white/90
                         transition-colors"
            >
              Close this tab
            </button>
          )}
        </div>

        {/* Additional help text */}
        <div className="mt-6 text-center">
          <p className="text-xs text-white/40">
            Powered by{" "}
            <span className="text-[#4AA8FF] font-semibold">NAVI</span>
          </p>
        </div>
      </div>
    </div>
  );
}

export default function SuccessPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-[#0B1324] via-[#070B12] to-[#070B12]">
        <div className="text-white">Loading...</div>
      </div>
    }>
      <SuccessContent />
    </Suspense>
  );
}
