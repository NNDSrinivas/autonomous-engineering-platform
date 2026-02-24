import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";
import { getSession } from "@auth0/nextjs-auth0/edge";

// Paths that require authentication
const protectedPaths = ["/app", "/profile", "/settings", "/dashboard"];

// Paths that should redirect authenticated users away
const authPaths = ["/login", "/signup", "/forgot-password"];

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const res = NextResponse.next();

  try {
    const session = await getSession(request, res);
    const isAuthenticated = !!session?.user;

    // Check if path is protected
    const isProtectedPath = protectedPaths.some((path) =>
      pathname.startsWith(path)
    );

    // Check if path is an auth page
    const isAuthPath = authPaths.some((path) => pathname.startsWith(path));

    // Redirect unauthenticated users away from protected paths
    if (isProtectedPath && !isAuthenticated) {
      const loginUrl = new URL("/login", request.url);
      loginUrl.searchParams.set("returnTo", pathname);
      return NextResponse.redirect(loginUrl);
    }

    // Redirect authenticated users away from auth pages
    if (isAuthPath && isAuthenticated) {
      return NextResponse.redirect(new URL("/app", request.url));
    }

    return res;
  } catch (error) {
    // If session check fails, allow the request to continue
    // The individual page will handle authentication
    return res;
  }
}

export const config = {
  matcher: [
    "/app",
    "/app/:path*",
    "/profile",
    "/profile/:path*",
    "/settings",
    "/settings/:path*",
    "/dashboard",
    "/dashboard/:path*",
    "/login",
    "/signup",
    "/forgot-password",
  ],
};
