import type { NextAuthConfig } from "next-auth";
import { authCookies } from "@/lib/auth-cookies";

const PROTECTED_PAGES = ["/chat", "/projects", "/settings"];
const PROTECTED_APIS = ["/api/chat", "/api/conversations", "/api/projects", "/api/ai-servers"];

function isProtectedPage(path: string) {
  return PROTECTED_PAGES.some((prefix) => path.startsWith(prefix));
}

function isProtectedApi(path: string) {
  return PROTECTED_APIS.some((prefix) => path.startsWith(prefix));
}

export const authConfig = {
  trustHost: true,
  secret: process.env.AUTH_SECRET ?? process.env.NEXTAUTH_SECRET,
  cookies: authCookies,
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt" as const,
  },
  callbacks: {
    authorized({ auth, request }) {
      const { pathname } = request.nextUrl;

      if (request.method === "OPTIONS") {
        return true;
      }

      if (pathname.startsWith("/api/auth")) {
        return true;
      }

      const isLoggedIn = !!auth?.user;
      const isAuthPage = pathname.startsWith("/login") || pathname.startsWith("/register");

      if (isAuthPage) {
        if (isLoggedIn) {
          return Response.redirect(new URL("/chat", request.nextUrl));
        }
        return true;
      }

      if (isProtectedApi(pathname)) {
        if (!isLoggedIn) {
          return Response.json({ error: "No autorizado" }, { status: 401 });
        }
        return true;
      }

      if (isProtectedPage(pathname)) {
        return isLoggedIn;
      }

      return true;
    },
    jwt({ token, user }) {
      if (user) {
        token.id = user.id;
        token.role = user.role;
        token.documentId = user.documentId;
      }
      return token;
    },
    session({ session, token }) {
      if (session.user) {
        session.user.id = token.id as string;
        session.user.role = token.role as string;
        session.user.documentId = token.documentId as string;
      }
      return session;
    },
  },
  providers: [],
} satisfies NextAuthConfig;
