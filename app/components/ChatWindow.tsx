"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";
import { ChatMessageBubble } from "@/app/components/chat/ChatMessageBubble";
import GlassButton from "@/app/components/ui/GlassButton";
import GlassCard from "@/app/components/ui/GlassCard";
import { useTheme } from "@/app/components/theme/ThemeProvider";
import type { BackgroundJob, MessageMetadata } from "@/lib/types";

const STREAMING_STORAGE_KEY = "gptenterprice-streaming";

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
  const { colors } = useTheme();
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadingLabel, setLoadingLabel] = useState("Pensando...");
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [jobStates, setJobStates] = useState<Record<string, JobRuntimeState>>({});
  const [streamingEnabled, setStreamingEnabled] = useState(true);
  const [streamHint, setStreamHint] = useState<string | null>(null);
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
          // siguiente tick reintenta
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
    try {
      const stored = localStorage.getItem(STREAMING_STORAGE_KEY);
      if (stored !== null) setStreamingEnabled(stored === "true");
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    return () => {
      Object.values(pollingRef.current).forEach(clearInterval);
      pollingRef.current = {};
    };
  }, []);

  const visibleMessages = conversation?.messages.filter((m) => m.role !== "TOOL") ?? [];
  const isBusy = loading || streamingContent !== null;

  useEffect(() => {
    const container = scrollRef.current;
    if (!container) return;
    container.scrollTo({ top: container.scrollHeight, behavior: "smooth" });
  }, [conversation?.messages, loading, jobStates, streamingContent]);

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!input.trim() || isBusy) return;

    const userText = input.trim();
    setInput("");
    setLoading(true);
    setLoadingLabel(looksLikeToolRequest(userText) ? "Consultando datos..." : "Pensando...");
    setStreamHint(null);
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

      const contentType = response.headers.get("content-type") ?? "";

      if (contentType.includes("text/event-stream") && response.body) {
        const animateTokens = streamingEnabled;
        if (animateTokens) {
          setLoading(false);
          setStreamingContent("");
        }

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
                message?: any;
                pendingJob?: BackgroundJob | null;
              };

              if (event.type === "token" && event.content) {
                if (animateTokens) {
                  setStreamingContent((current) => (current ?? "") + event.content);
                }
              } else if (event.type === "error" && event.message) {
                throw new Error(String(event.message));
              } else if (event.type === "done") {
                resolvedConversationId = event.conversationId ?? resolvedConversationId;
                assistantMessageId = event.message?.id ?? null;
                pendingJob = event.pendingJob ?? null;
              }
            } catch {
              // ignorar fragmentos SSE incompletos
            }
          }
        }

        setStreamingContent(null);
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
            : data?.error ?? `Error HTTP ${response.status}${target ? ` (${target})` : ""}`;
          throw new Error(message);
        }

        if (!conversationId) onConversationCreated(data.conversationId);

        await refreshConversation(data.conversationId);

        if (data.pendingJob?.id && data.message?.id) {
          setLoadingLabel("Generando archivo...");
          pollJob(data.pendingJob.id, data.message.id);
          setJobStates((current) => ({
            ...current,
            [data.pendingJob.id]: {
              status: data.pendingJob.status,
              progress: data.pendingJob.progress ?? 8,
              stage: data.pendingJob.stage ?? "En cola...",
            },
          }));
        }
      }
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Error desconocido");
    } finally {
      setLoading(false);
      setLoadingLabel("Pensando...");
      setStreamHint(null);
    }
  }

  return (
    <GlassCard className="flex h-full min-h-0 flex-col overflow-hidden">
      <div
        className="shrink-0 border-b px-5 py-4 backdrop-blur-xl"
        style={{ borderColor: colors.border, background: "rgba(255,255,255,0.03)" }}
      >
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[10px] uppercase tracking-[0.24em]" style={{ color: colors.textMuted }}>
              Conversación
            </p>
            <h2 className="text-lg font-semibold tracking-tight" style={{ color: colors.text }}>
              {conversation?.project.name ?? "Chat"}
            </h2>
          </div>
          <div className="flex items-center gap-2">
            <label
              className="flex cursor-pointer items-center gap-2 rounded-full border px-3 py-1 text-[11px]"
              style={{ borderColor: colors.border, color: colors.textSoft }}
              title="Híbrido automático: chat con streaming y tools sin cambiar este interruptor."
            >
              <input
                type="checkbox"
                checked={streamingEnabled}
                onChange={(e) => {
                  const next = e.target.checked;
                  setStreamingEnabled(next);
                  try {
                    localStorage.setItem(STREAMING_STORAGE_KEY, String(next));
                  } catch {
                    // ignore
                  }
                }}
                className="accent-violet-500"
              />
              Animación
            </label>
            <div
              className="rounded-full px-3 py-1 text-[11px] font-medium"
              style={{ background: colors.accentSoft, color: colors.accent }}
            >
              {conversation?.project.tools.length ?? 0} tools
            </div>
          </div>
        </div>
      </div>

      <div
        ref={scrollRef}
        className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-4 py-5 md:px-5"
      >
        {!conversationId && visibleMessages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="rounded-3xl border border-dashed p-8 text-center backdrop-blur-md"
            style={{ borderColor: colors.border, color: colors.textSoft, background: "rgba(255,255,255,0.03)" }}
          >
            <p className="text-sm">Prueba pedir un Excel de llamadas con fechas, por ejemplo:</p>
            <p className="mt-2 text-xs opacity-80">
              &quot;Dame todas las llamadas del 9 al 12 de julio de 2026 en Excel&quot;
            </p>
          </motion.div>
        ) : null}

        {visibleMessages.map((message) => {
          const jobId = message.metadata?.pending_job?.id;
          const runtime = jobId ? jobStates[jobId] : undefined;

          return (
            <ChatMessageBubble
              key={message.id}
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
          <ChatMessageBubble role="ASSISTANT" content={streamingContent} isStreaming />
        ) : null}

        {loading ? (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex justify-start">
            <div
              className="rounded-3xl rounded-bl-lg px-4 py-3 text-sm backdrop-blur-xl"
              style={{
                background: "rgba(255,255,255,0.06)",
                color: colors.textSoft,
                border: `1px solid ${colors.border}`,
              }}
            >
              <motion.span
                animate={{ opacity: [0.35, 1, 0.35] }}
                transition={{ duration: 1.2, repeat: Infinity }}
              >
                {loadingLabel}
              </motion.span>
            </div>
          </motion.div>
        ) : null}
      </div>

      {streamHint ? (
        <div
          className="mx-4 mb-2 rounded-2xl px-3 py-2 text-xs backdrop-blur-md md:mx-5"
          style={{ color: colors.textSoft, background: `${colors.accent}12`, border: `1px solid ${colors.border}` }}
        >
          {streamHint}
        </div>
      ) : null}

      {error ? (
        <div
          className="mx-4 mb-2 rounded-2xl px-3 py-2 text-sm backdrop-blur-md md:mx-5"
          style={{ color: colors.danger, background: `${colors.danger}12`, border: `1px solid ${colors.danger}33` }}
        >
          {error}
        </div>
      ) : null}

      <form
        onSubmit={handleSubmit}
        className="shrink-0 border-t p-4 backdrop-blur-xl md:p-5"
        style={{ borderColor: colors.border, background: "rgba(255,255,255,0.03)" }}
      >
        <div className="flex gap-3">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Escribe tu mensaje..."
            disabled={isBusy}
            className="flex-1 rounded-2xl border px-4 py-3 text-sm outline-none backdrop-blur-md transition focus:ring-2"
            style={{
              borderColor: colors.border,
              background: "rgba(255,255,255,0.05)",
              color: colors.text,
              boxShadow: "inset 0 1px 0 rgba(255,255,255,0.05)",
            }}
          />
          <GlassButton type="submit" disabled={isBusy || !input.trim()} className="px-5">
            Enviar
          </GlassButton>
        </div>
      </form>
    </GlassCard>
  );
}
