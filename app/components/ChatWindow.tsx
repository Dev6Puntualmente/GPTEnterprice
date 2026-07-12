"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import GlassCard from "@/app/components/ui/GlassCard";
import { useTheme } from "@/app/components/theme/ThemeProvider";

type Message = {
  id: string;
  role: "USER" | "ASSISTANT" | "TOOL" | "SYSTEM";
  content: string;
  metadata?: { model_used?: string; files?: string[] } | null;
};

type Conversation = {
  id: string;
  title: string;
  messages: Message[];
  project: {
    id: string;
    name: string;
    tools: Array<{ name: string; description: string }>;
  };
};

type ChatWindowProps = {
  conversationId: string | null;
  projectId: string;
  onConversationCreated: (conversationId: string) => void;
};

export function ChatWindow({
  conversationId,
  projectId,
  onConversationCreated,
}: ChatWindowProps) {
  const { colors } = useTheme();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!conversationId) {
      setConversation(null);
      return;
    }
    fetch(`/api/conversations/${conversationId}`)
      .then((response) => response.json())
      .then((data) => setConversation(data))
      .catch(() => setError("No se pudo cargar la conversación"));
  }, [conversationId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [conversation?.messages, loading]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!input.trim() || loading) return;

    const userText = input.trim();
    setInput("");
    setLoading(true);
    setError(null);

    const optimisticMessage: Message = {
      id: `temp-${Date.now()}`,
      role: "USER",
      content: userText,
    };

    setConversation((current) =>
      current
        ? { ...current, messages: [...current.messages, optimisticMessage] }
        : {
            id: "temp",
            title: userText.slice(0, 60),
            messages: [optimisticMessage],
            project: { id: projectId, name: "", tools: [] },
          },
    );

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          conversationId: conversationId ?? undefined,
          projectId,
          message: userText,
        }),
      });

      const data = await response.json().catch(() => null);
      if (!response.ok) {
        const target = data?.chatUrl ?? data?.agentApiUrl;
        const message = data?.detail
          ? `${data.error ?? "Error al enviar mensaje"}: ${data.detail}${target ? ` (${target})` : ""}`
          : data?.error ?? `Error HTTP ${response.status}${target ? ` (${target})` : ""}`;
        throw new Error(message);
      }

      if (!conversationId) onConversationCreated(data.conversationId);

      const refreshed = await fetch(`/api/conversations/${data.conversationId}`);
      setConversation(await refreshed.json());
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  const visibleMessages = conversation?.messages.filter((m) => m.role !== "TOOL") ?? [];

  return (
    <GlassCard className="flex h-full min-h-[70vh] flex-col overflow-hidden">
      <div className="border-b px-5 py-4 backdrop-blur-md" style={{ borderColor: colors.border }}>
        <h2 className="text-lg font-semibold" style={{ color: colors.text }}>
          {conversation?.project.name ?? "Chat"}
        </h2>
        {conversation?.project.tools.length ? (
          <p className="mt-1 text-xs" style={{ color: colors.textSoft }}>
            {conversation.project.tools.map((t) => t.name).join(" · ")}
          </p>
        ) : null}
      </div>

      <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
        {!conversationId && visibleMessages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-2xl border border-dashed p-8 text-center backdrop-blur-sm"
            style={{ borderColor: colors.border, color: colors.textSoft }}
          >
            Prueba: &quot;Dame el reporte de usuarios de 11:00 a 17:00 en Excel&quot;
          </motion.div>
        ) : null}

        <AnimatePresence initial={false}>
          {visibleMessages.map((message) => (
            <motion.div
              key={message.id}
              initial={{ opacity: 0, y: 12, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ type: "spring", stiffness: 320, damping: 28 }}
              className={`flex ${message.role === "USER" ? "justify-end" : "justify-start"}`}
            >
              <div
                className="max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 backdrop-blur-md"
                style={
                  message.role === "USER"
                    ? {
                        background: `linear-gradient(135deg, ${colors.accent}, #3b82f6)`,
                        color: "#fff",
                        boxShadow: `0 8px 24px ${colors.glow}`,
                      }
                    : {
                        background: colors.panelAlt,
                        color: colors.text,
                        border: `1px solid ${colors.border}`,
                      }
                }
              >
                <p className="whitespace-pre-wrap">{message.content}</p>
                {message.metadata?.files?.map((fileUrl) => (
                  <a
                    key={fileUrl}
                    href={fileUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-2 block rounded-lg px-3 py-2 text-xs underline opacity-90"
                  >
                    Descargar archivo
                  </a>
                ))}
                {message.metadata?.model_used ? (
                  <p className="mt-2 text-[10px] opacity-60">{message.metadata.model_used}</p>
                ) : null}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {loading ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex justify-start"
          >
            <div
              className="rounded-2xl px-4 py-3 text-sm backdrop-blur-md"
              style={{ background: colors.panelAlt, color: colors.textSoft }}
            >
              <motion.span
                animate={{ opacity: [0.4, 1, 0.4] }}
                transition={{ duration: 1.2, repeat: Infinity }}
              >
                Pensando...
              </motion.span>
            </div>
          </motion.div>
        ) : null}

        <div ref={bottomRef} />
      </div>

      {error ? (
        <div className="mx-5 mb-2 rounded-xl px-3 py-2 text-sm" style={{ color: colors.danger, background: `${colors.danger}15` }}>
          {error}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="border-t p-4 backdrop-blur-md" style={{ borderColor: colors.border }}>
        <div className="flex gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Pregunta algo o pide un reporte..."
            disabled={loading}
            className="flex-1 rounded-xl border px-4 py-3 text-sm outline-none backdrop-blur-md"
            style={{ borderColor: colors.border, background: colors.panelAlt, color: colors.text }}
          />
          <motion.button
            type="submit"
            disabled={loading || !input.trim()}
            whileHover={{ scale: 1.03 }}
            whileTap={{ scale: 0.97 }}
            className="rounded-xl px-5 py-3 text-sm font-semibold text-white disabled:opacity-40"
            style={{ background: colors.accent }}
          >
            Enviar
          </motion.button>
        </div>
      </form>
    </GlassCard>
  );
}
