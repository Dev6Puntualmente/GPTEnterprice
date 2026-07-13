"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { motion, AnimatePresence } from "framer-motion";
import GlassCard from "@/app/components/ui/GlassCard";
import ThemeToggle from "@/app/components/theme/ThemeToggle";
import { useTheme } from "@/app/components/theme/ThemeProvider";

type AiServer = {
  id: string;
  name: string;
  type: string;
  baseUrl: string;
  modelName: string;
  color: string;
  enabled: boolean;
  isDefault: boolean;
  hasApiKey: boolean;
};

type ProviderForm = {
  name: string;
  baseUrl: string;
  modelName: string;
  apiKey: string;
  color: string;
  enabled: boolean;
  isDefault: boolean;
};

const PHI_DEFAULTS: ProviderForm = {
  name: "Phi 3.5",
  baseUrl: "http://localhost:8002/v1",
  modelName: "Phi-3.5-mini-instruct",
  apiKey: "",
  color: "#8b5cf6",
  enabled: true,
  isDefault: true,
};

export default function AiServersClient() {
  const { colors } = useTheme();
  const [server, setServer] = useState<AiServer | null>(null);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<ProviderForm>(PHI_DEFAULTS);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function loadServer() {
    const response = await fetch("/api/ai-servers");
    const data = (await response.json()) as AiServer[];
    setServer(data[0] ?? null);
    setLoading(false);
  }

  useEffect(() => {
    loadServer();
  }, []);

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    try {
      const response = await fetch("/api/ai-servers/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          baseUrl: form.baseUrl,
          ...(form.apiKey.trim() ? { apiKey: form.apiKey.trim() } : {}),
        }),
      });
      const data = await response.json();
      setTestResult(data.ok ? "Conexión exitosa ✓" : data.error ?? "Error de conexión");
    } catch {
      setTestResult("No se pudo conectar");
    } finally {
      setTesting(false);
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);

    const method = server ? "PATCH" : "POST";
    const url = server ? `/api/ai-servers/${server.id}` : "/api/ai-servers";
    const payload: Record<string, unknown> = {
      name: form.name,
      baseUrl: form.baseUrl,
      modelName: form.modelName,
      color: form.color,
      enabled: form.enabled,
      isDefault: form.isDefault,
    };
    if (form.apiKey.trim()) {
      payload.apiKey = form.apiKey.trim();
    }

    await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    setSaving(false);
    setShowForm(false);
    setForm((current) => ({ ...current, apiKey: "" }));
    loadServer();
  }

  function openEdit() {
    if (!server) {
      setForm(PHI_DEFAULTS);
    } else {
      setForm({
        name: server.name,
        baseUrl: server.baseUrl,
        modelName: server.modelName,
        apiKey: "",
        color: server.color,
        enabled: server.enabled,
        isDefault: server.isDefault,
      });
    }
    setTestResult(null);
    setShowForm(true);
  }

  return (
    <div className="relative min-h-screen px-4 py-6 md:px-8">
      <div className="mx-auto max-w-3xl">
        <div className="mb-6 flex items-center justify-between gap-4">
          <div>
            <Link href="/chat" className="text-sm underline-offset-2 hover:underline" style={{ color: colors.textSoft }}>
              ← Volver al chat
            </Link>
            <h1 className="mt-2 text-2xl font-bold" style={{ color: colors.text }}>
              Proveedor de IA
            </h1>
            <p className="text-sm" style={{ color: colors.textSoft }}>
              URL, modelo y API Key vLLM — configurable por usuario
            </p>
          </div>
          <ThemeToggle />
        </div>

        <GlassCard className="mb-4 p-4">
          <p className="text-sm" style={{ color: colors.textSoft }}>
            La API Key de vLLM (la misma que --api-key al lanzar el servidor) se guarda aquí, asociada a tu cuenta.
            Ya no hace falta ponerlo en <code className="font-mono">.env</code>.
          </p>
        </GlassCard>

        {loading ? (
          <p style={{ color: colors.textSoft }}>Cargando proveedor...</p>
        ) : server ? (
          <GlassCard hover className="p-5">
            <div className="mb-3 flex items-start justify-between">
              <div className="flex items-center gap-3">
                <div
                  className="flex h-11 w-11 items-center justify-center rounded-xl text-xl"
                  style={{ background: `${server.color}22` }}
                >
                  ⚡
                </div>
                <div>
                  <h3 className="font-semibold" style={{ color: colors.text }}>
                    {server.name}
                  </h3>
                  <p className="text-xs" style={{ color: colors.textSoft }}>
                    {server.modelName}
                  </p>
                </div>
              </div>
              <span
                className="rounded-full px-2 py-1 text-[10px] font-medium uppercase"
                style={{
                  background: server.enabled ? `${colors.success}20` : `${colors.danger}20`,
                  color: server.enabled ? colors.success : colors.danger,
                }}
              >
                {server.enabled ? "Activo" : "Off"}
              </span>
            </div>

            <p className="truncate rounded-lg px-3 py-2 font-mono text-xs" style={{ background: colors.panelAlt, color: colors.textSoft }}>
              {server.baseUrl}
            </p>

            <p className="mt-2 text-xs" style={{ color: colors.textSoft }}>
              API Key vLLM: {server.hasApiKey ? "configurada ✓" : "no configurada"}
            </p>

            <div className="mt-4">
              <button
                type="button"
                onClick={openEdit}
                className="rounded-lg px-3 py-1.5 text-xs font-medium"
                style={{ background: colors.accentSoft, color: colors.accent }}
              >
                Editar proveedor
              </button>
            </div>
          </GlassCard>
        ) : (
          <GlassCard className="p-8 text-center">
            <p className="mb-4" style={{ color: colors.textSoft }}>
              No hay proveedor configurado. Agrega tu servidor vLLM para empezar a chatear.
            </p>
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              onClick={openEdit}
              className="rounded-xl px-4 py-2.5 text-sm font-semibold text-white"
              style={{ background: colors.accent, boxShadow: `0 8px 24px ${colors.glow}` }}
            >
              Configurar proveedor
            </motion.button>
          </GlassCard>
        )}
      </div>

      <AnimatePresence>
        {showForm ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: "rgba(0,0,0,0.55)", backdropFilter: "blur(8px)" }}
            onClick={() => setShowForm(false)}
          >
            <motion.div
              initial={{ scale: 0.92, opacity: 0, y: 20 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.92, opacity: 0, y: 20 }}
              transition={{ type: "spring", stiffness: 280, damping: 24 }}
              className="w-full max-w-lg rounded-2xl border p-6 backdrop-blur-xl"
              style={{ background: colors.panelSolid, borderColor: colors.border }}
              onClick={(event) => event.stopPropagation()}
            >
              <h2 className="mb-4 text-lg font-semibold" style={{ color: colors.text }}>
                {server ? "Editar proveedor" : "Configurar proveedor"}
              </h2>

              <form onSubmit={handleSubmit} className="space-y-3">
                <input
                  required
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Nombre (ej. Qwen remoto)"
                  className="w-full rounded-xl border px-4 py-2.5 text-sm"
                  style={{ borderColor: colors.border, background: colors.panelAlt, color: colors.text }}
                />
                <input
                  required
                  value={form.baseUrl}
                  onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
                  placeholder="URL base (http://148.251.183.33:8080/v1)"
                  className="w-full rounded-xl border px-4 py-2.5 text-sm font-mono"
                  style={{ borderColor: colors.border, background: colors.panelAlt, color: colors.text }}
                />
                <input
                  required
                  value={form.modelName}
                  onChange={(e) => setForm({ ...form, modelName: e.target.value })}
                  placeholder="Nombre del modelo (Qwen/Qwen2.5-3B-Instruct)"
                  className="w-full rounded-xl border px-4 py-2.5 text-sm"
                  style={{ borderColor: colors.border, background: colors.panelAlt, color: colors.text }}
                />
                <input
                  type="password"
                  value={form.apiKey}
                  onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
                  placeholder={
                    server?.hasApiKey
                      ? "API Key vLLM (deja vacío para mantener la actual)"
                      : "API Key vLLM — la misma que --api-key al lanzar el servidor"
                  }
                  autoComplete="off"
                  className="w-full rounded-xl border px-4 py-2.5 text-sm font-mono"
                  style={{ borderColor: colors.border, background: colors.panelAlt, color: colors.text }}
                />

                <div className="flex items-center gap-4">
                  <label className="flex items-center gap-2 text-sm" style={{ color: colors.textSoft }}>
                    <input
                      type="checkbox"
                      checked={form.enabled}
                      onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
                    />
                    Activo
                  </label>
                  <input
                    type="color"
                    value={form.color}
                    onChange={(e) => setForm({ ...form, color: e.target.value })}
                    className="h-8 w-10 cursor-pointer rounded"
                  />
                </div>

                {testResult ? (
                  <p className="text-sm" style={{ color: testResult.includes("✓") ? colors.success : colors.danger }}>
                    {testResult}
                  </p>
                ) : null}

                <div className="flex gap-2 pt-2">
                  <button
                    type="button"
                    onClick={handleTest}
                    disabled={testing}
                    className="rounded-xl border px-4 py-2 text-sm"
                    style={{ borderColor: colors.border, color: colors.textSoft }}
                  >
                    {testing ? "Probando..." : "Probar conexión"}
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="flex-1 rounded-xl py-2 text-sm font-semibold text-white"
                    style={{ background: colors.accent }}
                  >
                    {saving ? "Guardando..." : "Guardar"}
                  </button>
                </div>
              </form>
            </motion.div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
