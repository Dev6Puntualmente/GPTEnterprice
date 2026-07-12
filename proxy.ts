export { auth as proxy } from "@/auth";

export const config = {
  matcher: [
    "/chat/:path*",
    "/projects/:path*",
    "/settings/:path*",
    "/login",
    "/register",
    "/api/chat/:path*",
    "/api/conversations/:path*",
    "/api/projects/:path*",
    "/api/ai-servers/:path*",
  ],
};
