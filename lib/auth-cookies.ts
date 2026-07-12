import type { NextAuthConfig } from "next-auth";

/** Prefijo único — evita colisión con Qontrol u otras apps en localhost. */
const PREFIX = "ge";

const secure = process.env.NODE_ENV === "production";

export const authCookies: NonNullable<NextAuthConfig["cookies"]> = {
  sessionToken: {
    name: `${PREFIX}.session-token`,
    options: {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure,
    },
  },
  callbackUrl: {
    name: `${PREFIX}.callback-url`,
    options: {
      sameSite: "lax",
      path: "/",
      secure,
    },
  },
  csrfToken: {
    name: `${PREFIX}.csrf-token`,
    options: {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure,
    },
  },
  pkceCodeVerifier: {
    name: `${PREFIX}.pkce.code_verifier`,
    options: {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure,
      maxAge: 60 * 15,
    },
  },
  state: {
    name: `${PREFIX}.state`,
    options: {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure,
      maxAge: 60 * 15,
    },
  },
  nonce: {
    name: `${PREFIX}.nonce`,
    options: {
      httpOnly: true,
      sameSite: "lax",
      path: "/",
      secure,
    },
  },
};
