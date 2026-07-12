import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { PrismaAdapter } from "@auth/prisma-adapter";
import bcrypt from "bcryptjs";
import { authConfig } from "@/auth.config";
import { prisma } from "@/lib/prisma";

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,
  adapter: PrismaAdapter(prisma),
  providers: [
    Credentials({
      name: "credentials",
      credentials: {
        documentId: { label: "Documento", type: "text" },
        password: { label: "Contraseña", type: "password" },
      },
      async authorize(credentials) {
        const documentId = credentials?.documentId?.toString().trim().replace(/\D/g, "");
        const password = credentials?.password?.toString() ?? "";
        if (!documentId || !password) return null;

        const user = await prisma.user.findUnique({ where: { documentId } });
        if (!user?.passwordHash) return null;

        const valid = await bcrypt.compare(password, user.passwordHash);
        if (!valid) return null;

        return {
          id: user.id,
          documentId: user.documentId,
          email: user.email,
          name: user.name,
          role: user.role,
        };
      },
    }),
  ],
});
