import { handleAuth, handleLogin, handleCallback, handleLogout } from "@auth0/nextjs-auth0";
import { Session } from "@auth0/nextjs-auth0";
import type { NextRequest } from "next/server";
import type { NextApiRequest } from "next";
import { validateReturnTo } from "@/lib/auth/validation";

export const GET = handleAuth({
  login: handleLogin((req: NextRequest | NextApiRequest) => {
    // Get connection from query params for direct social login
    // Handle both App Router (NextRequest) and Pages Router (NextApiRequest)
    let connection: string | null = null;
    let returnToParam: string | null = null;

    if ('nextUrl' in req) {
      // App Router (NextRequest)
      const searchParams = req.nextUrl.searchParams;
      connection = searchParams.get("connection");
      returnToParam = searchParams.get("returnTo");
    } else {
      // Pages Router (NextApiRequest) - use query object
      const query = req.query as { connection?: string; returnTo?: string };
      connection = query.connection || null;
      returnToParam = query.returnTo || null;
    }

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
