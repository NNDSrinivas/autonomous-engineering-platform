import { handleAuth, handleLogin, handleCallback, handleLogout } from "@auth0/nextjs-auth0";
import { Session } from "@auth0/nextjs-auth0";
import { NextRequest } from "next/server";
import { NextApiRequest } from "next";

export const GET = handleAuth({
  login: handleLogin((req) => {
    // Get connection from query params for direct social login
    // Handle both NextRequest (App Router) and NextApiRequest (Pages Router)
    const searchParams = 'nextUrl' in req
      ? req.nextUrl.searchParams
      : new URLSearchParams(req.url?.split('?')[1] || '');

    const connection = searchParams.get("connection");
    // Validate returnTo parameter to prevent open redirect vulnerability
    const returnToParam = searchParams.get("returnTo");
    const returnTo = (returnToParam && returnToParam.startsWith("/"))
      ? returnToParam
      : "/app/chats";

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
