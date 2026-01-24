import "./globals.css";
import { UserProvider } from "@auth0/nextjs-auth0/client";

export const metadata = {
  title: "NAVI | AI-Powered Engineering Assistant",
  description: "Your intelligent pair programming companion",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body>
        <UserProvider>{children}</UserProvider>
      </body>
    </html>
  );
}
