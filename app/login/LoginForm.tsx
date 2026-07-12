"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { signIn } from "next-auth/react";
import GlassCard from "@/app/components/ui/GlassCard";
import ThemeToggle from "@/app/components/theme/ThemeToggle";
import { useTheme } from "@/app/components/theme/ThemeProvider";

export default function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") ?? "/chat";
  const { colors } = useTheme();

  const [documentId, setDocumentId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const result = await signIn("credentials", {
        documentId: documentId.trim().replace(/\D/g, ""),
        password,
        redirect: false,
      });

      if (result?.error) {
        setError("Documento o contraseña incorrectos");
        return;
      }

      router.push(callbackUrl);
      router.refresh();
    } catch {
      setError("No se pudo iniciar sesión");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center px-6 py-10">
      <div className="absolute right-6 top-6">
        <ThemeToggle />
      </div>

      <GlassCard className="w-full max-w-md p-8">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 }}
          className="mb-8 text-center"
        >
          <motion.div
            className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl text-2xl"
            style={{ background: colors.accentSoft }}
            animate={{ rotate: [0, 3, -3, 0] }}
            transition={{ duration: 6, repeat: Infinity }}
          >
            🤖
          </motion.div>
          <p className="text-xs uppercase tracking-[0.2em]" style={{ color: colors.textMuted }}>
            GPTEnterprice
          </p>
          <h1 className="mt-2 text-2xl font-semibold" style={{ color: colors.text }}>
            Iniciar sesión
          </h1>
          <p className="mt-2 text-sm" style={{ color: colors.textSoft }}>
            Agente interno con function calling
          </p>
        </motion.div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium" style={{ color: colors.textSoft }}>
              Documento de identidad
            </label>
            <input
              type="text"
              inputMode="numeric"
              required
              autoComplete="username"
              value={documentId}
              onChange={(event) => setDocumentId(event.target.value)}
              className="w-full rounded-xl border px-4 py-3 text-sm outline-none backdrop-blur-md transition focus:ring-2"
              style={{
                borderColor: colors.border,
                background: colors.panelAlt,
                color: colors.text,
              }}
              placeholder="1000000001"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm font-medium" style={{ color: colors.textSoft }}>
              Contraseña
            </label>
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="w-full rounded-xl border px-4 py-3 text-sm outline-none backdrop-blur-md transition focus:ring-2"
              style={{
                borderColor: colors.border,
                background: colors.panelAlt,
                color: colors.text,
              }}
              placeholder="••••••••"
            />
          </div>

          {error ? (
            <motion.p
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              className="rounded-xl border px-4 py-3 text-sm"
              style={{
                borderColor: `${colors.danger}40`,
                background: `${colors.danger}15`,
                color: colors.danger,
              }}
            >
              {error}
            </motion.p>
          ) : null}

          <motion.button
            type="submit"
            disabled={loading}
            whileHover={{ scale: loading ? 1 : 1.02 }}
            whileTap={{ scale: loading ? 1 : 0.98 }}
            className="w-full rounded-xl px-4 py-3 text-sm font-semibold text-white disabled:opacity-50"
            style={{
              background: `linear-gradient(135deg, ${colors.accent}, #3b82f6)`,
              boxShadow: `0 12px 30px ${colors.glow}`,
            }}
          >
            {loading ? "Entrando..." : "Entrar"}
          </motion.button>
        </form>

        <p className="mt-6 text-center text-sm" style={{ color: colors.textSoft }}>
          <Link href="/register" className="underline underline-offset-2" style={{ color: colors.accent }}>
            Crear cuenta admin inicial
          </Link>
        </p>
      </GlassCard>
    </div>
  );
}
