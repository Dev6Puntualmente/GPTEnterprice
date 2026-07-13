"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ChatMessageBubble } from "@/app/components/chat/ChatMessageBubble";
import GlassButton from "@/app/components/ui/GlassButton";
import ParticleField from "@/app/components/ui/ParticleField";
import { useTheme } from "@/app/components/theme/ThemeProvider";
import type { BackgroundJob, MessageMetadata } from "@/lib/types";

function looksLikeToolRequest(text: string): boolean {
  return /busca(?:r|a)|gesti[oó]n|crm\b|llamad|reporte|estad[ií]stica|poster|dashboard|tipific|flujo/i.test(
    text,
  );
}

type Message = {
  id: string;
  role: "USER" | "ASSISTANT" | "TOOL" | "SYSTEM";
  content: string;
  metadata?: MessageMetadata | null;
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

type JobRuntimeState = {
  status: BackgroundJob["status"];
  progress: number;
  stage: string;
  fileUrl?: string | null;
  error?: string | null;
};

type ChatWindowProps = {
  conversationId: string | null;
  projectId: string;
  onConversationCreated: (conversationId: string) => void;
};

const POLL_MS = 400;

export function ChatWindow({
  conversationId,
  projectId,
  onConversationCreated,
}: ChatWindowProps) {
  const { colors, mode } = useTheme();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("Pensando...");
  const [streamPhase, setStreamPhase] = useState<"idle" | "working" | "typing">("idle");
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const pendingTokensRef = useRef("");
  const flushTokensRef = useRef<number | null>(null);
  const typingStartedRef = useRef(false);
  const [error, setError] = useState<string | null>(null);
  const [jobStates, setJobStates] = useState<Record<string, JobRuntimeState>>({});
  const scrollRef = useRef<HTMLDivElement>(null);
  const pollingRef = useRef<Record<string, ReturnType<typeof setInterval>>>({});
  const conversationIdRef = useRef(conversationId);
  conversationIdRef.current = conversationId;

  const refreshConversation = useCallback(async (id: string) => {
    const response = await fetch(`/api/conversations/${id}`, { cache: "no-store" });
    if (!response.ok) return;
    setConversation(await response.json());
  }, []);

  const patchMessageMetadata = useCallback(
    (messageId: string, metadata: Partial<MessageMetadata>) => {
      setConversation((current) => {
        if (!current) return current;
        return {
          ...current,
          messages: current.messages.map((message) =>
            message.id === messageId
              ? {
                  ...message,
                  metadata: { ...(message.metadata ?? {}), ...metadata },
                }
              : message,
          ),
        };
      });
    },
    [],
  );

  const persistJobCompletion = useCallback(
    async (messageId: string, job: BackgroundJob) => {
      const fileUrl = job.result?.url;
      patchMessageMetadata(messageId, {
        job_status: job.status,
        job_progress: job.progress,
        job_stage: job.stage,
        files: fileUrl ? [fileUrl] : [],
      });

      await fetch(`/api/messages/${messageId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          metadata: {
            job_status: job.status,
            job_progress: job.progress,
            job_stage: job.stage,
            files: fileUrl ? [fileUrl] : [],
          },
        }),
      });
    },
    [patchMessageMetadata],
  );

  const pollJob = useCallback(
    (jobId: string, messageId: string) => {
      if (pollingRef.current[jobId]) return;

      const tick = async () => {
        try {
          const response = await fetch(`/api/jobs/${jobId}`, { cache: "no-store" });
          if (!response.ok) return;

          const job = (await response.json()) as BackgroundJob;
          const fileUrl = job.result?.url ?? null;

          setJobStates((current) => ({
            ...current,
            [jobId]: {
              status: job.status,
              progress: job.progress ?? 0,
              stage: job.stage ?? "Procesando...",
              fileUrl,
              error: job.error ?? null,
            },
          }));

          patchMessageMetadata(messageId, {
            job_status: job.status,
            job_progress: job.progress,
            job_stage: job.stage,
          });

          if (job.status === "SUCCEEDED" || job.status === "FAILED") {
            clearInterval(pollingRef.current[jobId]);
            delete pollingRef.current[jobId];
            await persistJobCompletion(messageId, job);
            const convId = conversationIdRef.current;
            if (convId) await refreshConversation(convId);
          }
        } catch {
          // siguiente tick
        }
      };

      void tick();
      pollingRef.current[jobId] = setInterval(() => void tick(), POLL_MS);
    },
    [patchMessageMetadata, persistJobCompletion, refreshConversation],
  );

  useEffect(() => {
    if (!conversationId) {
      setConversation(null);
      return;
    }
    refreshConversation(conversationId).catch(() => setError("No se pudo cargar la conversación"));
  }, [conversationId, refreshConversation]);

  useEffect(() => {
    if (!conversation) return;
    for (const message of conversation.messages) {
      const jobId = message.metadata?.pending_job?.id;
      const terminal =
        message.metadata?.job_status === "SUCCEEDED" ||
        message.metadata?.job_status === "FAILED" ||
        Boolean(message.metadata?.files?.length);
      if (jobId && !pollingRef.current[jobId] && !terminal) {
        pollJob(jobId, message.id);
      }
    }
  }, [conversation, pollJob]);

  useEffect(() => {
    return () => {
      Object.values(pollingRef.current).forEach(clearInterval);
      pollingRef.current = {};
    };
  }, []);

  const visibleMessages = conversation?.messages.filter((m) => m.role !== "TOOL") ?? [];
  const isBusy = loading || streamPhase !== "idle";

  const flushPendingTokens = useCallback(() => {
    if (!pendingTokensRef.current) return;
    const chunk = pendingTokensRef.current;
    pendingTokensRef.current = "";
    setStreamingContent((current) => (current ?? "") + chunk);
  }, []);

  useEffect(() => {
    if (streamPhase !== "typing") return;
    const intervalId = window.setInterval(() => {
      flushPendingTokens();
    }, 32);
    return () => window.clearInterval(intervalId);
  }, [streamPhase, flushPendingTokens]);

  useEffect(() => {
    return () => {
      if (flushTokensRef.current !== null) {
        cancelAnimationFrame(flushTokensRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [conversation?.messages, loading, jobStates, streamingContent, streamPhase, loadingLabel]);

  async function sendChatRequest(userText: string, attempt = 0): Promise<Response> {
    const response = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        conversationId: conversationId ?? undefined,
        projectId,
        message: userText,
        stream: true,
      }),
    });

    if (!response.ok && attempt < 1) {
      const data = await response.json().catch(() => null);
      const detail = String(data?.detail ?? data?.error ?? "");
      if (/fetch failed|ECONNREFUSED|contactar FastAPI|502/i.test(detail)) {
        setLoadingLabel("Reconectando con el agente...");
        await new Promise((resolve) => setTimeout(resolve, 900));
        return sendChatRequest(userText, attempt + 1);
      }
    }

    return response;
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!input.trim() || isBusy) return;

    const userText = input.trim();
    setInput("");
    setLoading(true);
    setStreamPhase("working");
    setLoadingLabel(looksLikeToolRequest(userText) ? "Consultando datos..." : "Pensando...");
    setStreamingContent(null);
    pendingTokensRef.current = "";
    typingStartedRef.current = false;
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
      const response = await sendChatRequest(userText);

      const contentType = response.headers.get("content-type") ?? "";

      if (contentType.includes("text/event-stream") && response.body) {
        setStreamPhase("working");

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let resolvedConversationId = conversationId ?? null;
        let pendingJob: BackgroundJob | null = null;
        let assistantMessageId: string | null = null;

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });

          const parts = buffer.split("\n\n");
          buffer = parts.pop() ?? "";

          for (const part of parts) {
            const line = part.split("\n").find((entry) => entry.startsWith("data: "));
            if (!line) continue;
            try {
              const event = JSON.parse(line.slice(6)) as {
                type: string;
                content?: string;
                conversationId?: string;
                message?: { id?: string };
                pendingJob?: BackgroundJob | null;
              };

              if (event.type === "token" && event.content) {
                if (!typingStartedRef.current) {
                  typingStartedRef.current = true;
                  setStreamPhase("typing");
                  setLoading(false);
                  setStreamingContent("");
                }
                pendingTokensRef.current += event.content;
              } else if (event.type === "status" && event.content) {
                setStreamPhase("working");
                setLoadingLabel(event.content);
              } else if (event.type === "error" && event.message) {
                throw new Error(String(event.message));
              } else if (event.type === "done") {
                resolvedConversationId = event.conversationId ?? resolvedConversationId;
                assistantMessageId = event.message?.id ?? null;
                pendingJob = event.pendingJob ?? null;
              }
            } catch (parseError) {
              if (parseError instanceof Error && parseError.message !== "Unexpected end of JSON input") {
                throw parseError;
              }
            }
          }
        }

        flushPendingTokens();
        setStreamingContent(null);
        setStreamPhase("idle");
        setLoading(false);

        if (resolvedConversationId) {
          if (!conversationId) onConversationCreated(resolvedConversationId);
          await refreshConversation(resolvedConversationId);
        }

        if (pendingJob?.id && assistantMessageId) {
          setLoadingLabel("Generando archivo...");
          pollJob(pendingJob.id, assistantMessageId);
          setJobStates((current) => ({
            ...current,
            [pendingJob!.id]: {
              status: pendingJob!.status,
              progress: pendingJob!.progress ?? 8,
              stage: pendingJob!.stage ?? "En cola...",
            },
          }));
        }
      } else {
        const data = await response.json().catch(() => null);
        if (!response.ok) {
          const target = data?.chatUrl ?? data?.agentApiUrl;
          const message = data?.detail
            ? `${data.error ?? "Error al enviar mensaje"}: ${data.detail}${target ? ` (${target})` : ""}`
            : data?.error ?? `Error HTTP ${response.status}`;
          throw new Error(message);
        }

        if (!conversationId) onConversationCreated(data.conversationId);
        await refreshConversation(data.conversationId);

        if (data.pendingJob?.id && data.message?.id) {
          pollJob(data.pendingJob.id, data.message.id);
        }
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Error desconocido");
    } finally {
      setLoading(false);
      setStreamPhase("idle");
      setStreamingContent(null);
      typingStartedRef.current = false;
      pendingTokensRef.current = "";
      setLoadingLabel("Pensando...");
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="flex h-full min-h-0 min-w-0 flex-col overflow-hidden rounded-2xl border"
      style={{
        background: mode === "light" ? "rgba(255,255,255,0.72)" : colors.panel,
        borderColor: colors.border,
        boxShadow: colors.shadowLg ?? colors.shadow,
        backdropFilter: mode === "light" ? "blur(12px)" : undefined,
      }}
    >
      {/* Header */}
      <header
        className="relative flex shrink-0 items-center justify-between gap-3 overflow-hidden border-b px-4 py-3 sm:px-5"
        style={{ borderColor: colors.border, background: colors.surfaceMuted }}
      >
        <motion.div
          className="pointer-events-none absolute inset-0 opacity-40"
          style={{
            background: `linear-gradient(90deg, transparent, ${colors.accentSoft}, transparent)`,
          }}
          animate={{ x: ["-100%", "100%"] }}
          transition={{ duration: 5, repeat: Infinity, ease: "linear" }}
        />
        <div className="relative">
          <h2 className="text-base font-semibold tracking-tight" style={{ color: colors.text }}>
            {conversation?.project.name ?? "Nueva conversación"}
          </h2>
          <p className="flex items-center gap-1.5 text-xs" style={{ color: colors.textMuted }}>
            <motion.span
              className="inline-block h-1.5 w-1.5 rounded-full"
              style={{ background: colors.success }}
              animate={{ scale: [1, 1.35, 1], opacity: [0.7, 1, 0.7] }}
              transition={{ duration: 2, repeat: Infinity }}
            />
            {conversation?.project.tools.length ?? 0} herramientas · agente IA decide
          </p>
        </div>
      </header>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="relative min-h-0 min-w-0 flex-1 space-y-3 overflow-x-hidden overflow-y-auto overscroll-contain px-3 py-4 sm:px-5"
        style={{ background: mode === "light" ? "transparent" : "transparent" }}
      >
        <ParticleField density={28} />
        {!conversationId && visibleMessages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="relative mx-auto max-w-md rounded-xl border border-dashed p-8 text-center"
            style={{
              borderColor: colors.borderStrong,
              background: colors.surface,
              color: colors.textSoft,
            }}
          >
            <p className="text-sm font-medium" style={{ color: colors.text }}>
              ¿En qué te ayudo?
            </p>
            <p className="mt-2 text-xs leading-relaxed">
              Prueba: &quot;Busca el cliente con cédula 1140915961&quot; o &quot;Dashboard WhatsApp de esta semana&quot;
            </p>
          </motion.div>
        ) : null}

        {visibleMessages.map((message, index) => {
          const jobId = message.metadata?.pending_job?.id;
          const runtime = jobId ? jobStates[jobId] : undefined;
          return (
            <ChatMessageBubble
              key={message.id}
              index={index}
              role={message.role === "USER" ? "USER" : "ASSISTANT"}
              content={message.content}
              metadata={message.metadata}
              jobState={
                runtime
                  ? {
                      status: runtime.status,
                      progress: runtime.progress,
                      stage: runtime.stage,
                      fileUrl: runtime.fileUrl,
                      error: runtime.error,
                    }
                  : undefined
              }
            />
          );
        })}

        {streamingContent !== null ? (
          <ChatMessageBubble
            key="streaming-assistant"
            role="ASSISTANT"
            content={streamingContent}
            isStreaming
            streamPhase={streamPhase}
          />
        ) : null}

        {streamPhase === "working" ? (
          <div className="flex justify-start">
            <div
              className="flex max-w-md items-center gap-2.5 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm"
              style={{
                background: colors.surface,
                color: colors.textMuted,
                border: `1px solid ${colors.border}`,
              }}
            >
              <span className="inline-flex gap-1" aria-hidden>
                {[0, 1, 2].map((dot) => (
                  <span
                    key={dot}
                    className="inline-block h-1.5 w-1.5 animate-pulse rounded-full"
                    style={{
                      background: colors.accent,
                      animationDelay: `${dot * 180}ms`,
                    }}
                  />
                ))}
              </span>
              <span style={{ color: colors.text }}>{loadingLabel}</span>
            </div>
          </div>
        ) : null}

        {loading && streamPhase !== "working" ? (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="relative flex justify-start"
          >
            <div
              className="flex items-center gap-2 rounded-2xl rounded-bl-md px-4 py-2.5 text-sm"
              style={{
                background: colors.surface,
                color: colors.textMuted,
                border: `1px solid ${colors.border}`,
                boxShadow: mode === "light" ? "0 4px 16px rgba(15,23,42,0.05)" : undefined,
              }}
            >
              <motion.span
                className="flex gap-1"
                aria-hidden
              >
                {[0, 1, 2].map((dot) => (
                  <motion.span
                    key={dot}
                    className="inline-block h-1.5 w-1.5 rounded-full"
                    style={{ background: colors.accent }}
                    animate={{ y: [0, -4, 0], opacity: [0.4, 1, 0.4] }}
                    transition={{ duration: 0.9, repeat: Infinity, delay: dot * 0.15 }}
                  />
                ))}
              </motion.span>
              <motion.span
                animate={{ opacity: [0.5, 1, 0.5] }}
                transition={{ duration: 1.4, repeat: Infinity }}
              >
                {loadingLabel}
              </motion.span>
            </div>
          </motion.div>
        ) : null}
      </div>

      {error ? (
        <div
          className="mx-3 mb-2 rounded-lg px-3 py-2 text-sm sm:mx-5"
          style={{
            color: colors.danger,
            background: `${colors.danger}10`,
            border: `1px solid ${colors.danger}25`,
          }}
        >
          {error}
        </div>
      ) : null}

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="shrink-0 border-t p-3 sm:p-4"
        style={{ borderColor: colors.border, background: colors.panel }}
      >
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Escribe tu mensaje..."
            disabled={isBusy}
            className="min-w-0 flex-1 rounded-xl border px-4 py-2.5 text-sm outline-none transition focus:ring-2"
            style={{
              borderColor: colors.borderStrong,
              background: colors.input,
              color: colors.text,
              boxShadow: mode === "light" ? "inset 0 1px 2px rgba(15,23,42,0.04)" : "none",
            }}
          />
          <GlassButton type="submit" disabled={isBusy || !input.trim()} className="shrink-0 px-5">
            <span className="hidden sm:inline">Enviar</span>
            <span className="sm:hidden">→</span>
          </GlassButton>
        </div>
      </form>
    </motion.div>
  );
}
