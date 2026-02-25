import { handleAuth, handleLogin, handleCallback, handleLogout } from "@auth0/nextjs-auth0";
import { Session } from "@auth0/nextjs-auth0";
import type { NextRequest } from "next/server";
import type { NextApiRequest } from "next";
import { validateReturnTo } from "@/lib/auth/validation";

export const GET = handleAuth({
  login: handleLogin((req: NextRequest | NextApiRequest) => {
    // Get connection from query params for direct social login
    const searchParams = (req as NextRequest).nextUrl?.searchParams;

    const connection = searchParams.get("connection");
    const returnToParam = searchParams.get("returnTo");
    const returnTo = validateReturnTo(returnToParam, "/app/chats");

    return {
      authorizationParams: {
        audience: process.env.AUTH0_AUDIENCE,
        scope: "openid profile email offline_access",
        ...(connection && { connection }),
      },
      returnTo,
    };
  }),
  callback: handleCallback({
    afterCallback: async (
      _req: NextRequest | NextApiRequest,
      session: Session
    ): Promise<Session> => {
      // Sync user to backend database after successful authentication
      try {
        const backendUrl = process.env.BACKEND_URL || "http://localhost:8002";
        await fetch(`${backendUrl}/api/users/sync`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${session.accessToken}`,
          },
          body: JSON.stringify({
            sub: session.user.sub,
            email: session.user.email,
            name: session.user.name,
            org: session.user["https://navralabs.com/org"] || "public",
          }),
        });
      } catch (error) {
        // Log error but don't fail the callback
        console.error("Failed to sync user to backend:", error);
      }
      return session;
    },
  }),
  logout: handleLogout({
    returnTo: "/",
  }),
});

export const POST = handleAuth();
