"use client";

import { FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import GlassCard from "@/app/components/ui/GlassCard";
import ThemeToggle from "@/app/components/theme/ThemeToggle";
import { useTheme } from "@/app/components/theme/ThemeProvider";

export default function RegisterPage() {
  const router = useRouter();
  const { colors } = useTheme();
  const [name, setName] = useState("");
  const [documentId, setDocumentId] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError("");
    setLoading(true);

    try {
      const response = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          documentId: documentId.trim().replace(/\D/g, ""),
          password,
        }),
      });

      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? "No se pudo registrar");

      router.push("/login");
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Error desconocido");
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
        <div className="mb-8 text-center">
          <h1 className="text-2xl font-semibold" style={{ color: colors.text }}>
            Crear admin inicial
          </h1>
          <p className="mt-2 text-sm" style={{ color: colors.textSoft }}>
            Solo disponible si aún no existe ningún administrador.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <input
            type="text"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Nombre completo"
            className="w-full rounded-xl border px-4 py-3 text-sm backdrop-blur-md"
            style={{ borderColor: colors.border, background: colors.panelAlt, color: colors.text }}
          />
          <input
            type="text"
            inputMode="numeric"
            required
            value={documentId}
            onChange={(event) => setDocumentId(event.target.value)}
            placeholder="Documento de identidad"
            className="w-full rounded-xl border px-4 py-3 text-sm backdrop-blur-md"
            style={{ borderColor: colors.border, background: colors.panelAlt, color: colors.text }}
          />
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="Contraseña (mín. 8)"
            className="w-full rounded-xl border px-4 py-3 text-sm backdrop-blur-md"
            style={{ borderColor: colors.border, background: colors.panelAlt, color: colors.text }}
          />

          {error ? (
            <p className="rounded-xl border px-4 py-3 text-sm" style={{ color: colors.danger }}>
              {error}
            </p>
          ) : null}

          <motion.button
            type="submit"
            disabled={loading}
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="w-full rounded-xl px-4 py-3 text-sm font-semibold text-white"
            style={{ background: colors.accent }}
          >
            {loading ? "Creando..." : "Registrar"}
          </motion.button>
        </form>

        <p className="mt-6 text-center text-sm" style={{ color: colors.textSoft }}>
          <Link href="/login" className="underline underline-offset-2">
            Volver al login
          </Link>
        </p>
      </GlassCard>
    </div>
  );
}
