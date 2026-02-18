import React from "react";
import { Space_Grotesk, IBM_Plex_Mono } from "next/font/google";

const authDisplay = Space_Grotesk({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-auth-display",
});

const authMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-auth-mono",
});

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div
      className={`${authDisplay.variable} ${authMono.variable} relative min-h-screen overflow-hidden bg-background px-2 py-3 sm:px-4 sm:py-6`}
    >
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_20%_18%,hsl(192_96%_60%/.12),transparent_48%),radial-gradient(circle_at_85%_14%,hsl(222_95%_63%/.16),transparent_58%),linear-gradient(180deg,hsl(var(--background))_0%,hsl(220_32%_5%)_100%)]" />
      <div className="relative z-10 flex min-h-screen items-center justify-center">
        {children}
      </div>
    </div>
  );
}
