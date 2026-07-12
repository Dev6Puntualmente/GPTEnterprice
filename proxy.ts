import { NextResponse } from "next/server";
import { auth } from "@/auth";

export const proxy = auth((req) => {
  const { nextUrl } = req;
  const isLoggedIn = !!req.auth;
  const isAuthPage =
    nextUrl.pathname.startsWith("/login") || nextUrl.pathname.startsWith("/register");

  const isProtectedPage =
    nextUrl.pathname.startsWith("/chat") || nextUrl.pathname.startsWith("/projects");

  const isProtectedApi =
    nextUrl.pathname.startsWith("/api/chat") ||
    nextUrl.pathname.startsWith("/api/conversations") ||
    nextUrl.pathname.startsWith("/api/projects");

  if ((isProtectedPage || isProtectedApi) && !isLoggedIn) {
    if (isProtectedApi) {
      return NextResponse.json({ error: "No autorizado" }, { status: 401 });
    }

    const login = new URL("/login", nextUrl.origin);
    login.searchParams.set("callbackUrl", nextUrl.pathname);
    return NextResponse.redirect(login);
  }

  if (isLoggedIn && isAuthPage) {
    return NextResponse.redirect(new URL("/chat", nextUrl.origin));
  }

  return NextResponse.next();
});

export const config = {
  matcher: [
    "/chat/:path*",
    "/projects/:path*",
    "/login",
    "/register",
    "/api/chat/:path*",
    "/api/conversations/:path*",
    "/api/projects/:path*",
  ],
};
