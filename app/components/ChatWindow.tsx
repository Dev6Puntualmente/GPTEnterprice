"use client";

import { useEffect, useRef, useState } from "react";

type Message = {
  id: string;
  role: "USER" | "ASSISTANT" | "TOOL" | "SYSTEM";
  content: string;
  metadata?: {
    model_used?: string;
    files?: string[];
  } | null;
  toolName?: string | null;
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

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error ?? "Error al enviar mensaje");
      }

      if (!conversationId) {
        onConversationCreated(data.conversationId);
      }

      const refreshed = await fetch(`/api/conversations/${data.conversationId}`);
      const refreshedData = await refreshed.json();
      setConversation(refreshedData);
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : "Error desconocido");
    } finally {
      setLoading(false);
    }
  }

  const visibleMessages = conversation?.messages.filter((message) => message.role !== "TOOL") ?? [];

  return (
    <div className="flex h-full flex-col rounded-2xl border border-zinc-200 bg-white shadow-sm dark:border-zinc-800 dark:bg-zinc-950">
      <div className="border-b border-zinc-200 px-5 py-4 dark:border-zinc-800">
        <h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-50">
          {conversation?.project.name ?? "Chat"}
        </h2>
        {conversation?.project.tools.length ? (
          <p className="mt-1 text-sm text-zinc-500">
            Tools: {conversation.project.tools.map((tool) => tool.name).join(", ")}
          </p>
        ) : null}
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto px-5 py-4">
        {!conversationId && visibleMessages.length === 0 ? (
          <div className="rounded-xl border border-dashed border-zinc-300 p-8 text-center dark:border-zinc-700">
            <p className="text-zinc-600 dark:text-zinc-400">
              Escribe algo como:{" "}
              <span className="font-medium text-zinc-900 dark:text-zinc-100">
                &quot;Dame el reporte de usuarios de 11:00 a 17:00 en Excel&quot;
              </span>
            </p>
          </div>
        ) : null}

        {visibleMessages.map((message) => (
          <div
            key={message.id}
            className={`flex ${message.role === "USER" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-6 ${
                message.role === "USER"
                  ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                  : "bg-zinc-100 text-zinc-900 dark:bg-zinc-900 dark:text-zinc-100"
              }`}
            >
              <p className="whitespace-pre-wrap">{message.content}</p>
              {message.metadata?.files?.length ? (
                <div className="mt-3 space-y-2">
                  {message.metadata.files.map((fileUrl) => (
                    <a
                      key={fileUrl}
                      href={fileUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="block rounded-lg bg-white/10 px-3 py-2 text-xs underline"
                    >
                      Descargar archivo
                    </a>
                  ))}
                </div>
              ) : null}
              {message.metadata?.model_used ? (
                <p className="mt-2 text-xs opacity-60">Modelo: {message.metadata.model_used}</p>
              ) : null}
            </div>
          </div>
        ))}

        {loading ? (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-zinc-100 px-4 py-3 text-sm text-zinc-500 dark:bg-zinc-900">
              Pensando...
            </div>
          </div>
        ) : null}

        <div ref={bottomRef} />
      </div>

      {error ? (
        <div className="mx-5 mb-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-300">
          {error}
        </div>
      ) : null}

      <form onSubmit={handleSubmit} className="border-t border-zinc-200 p-4 dark:border-zinc-800">
        <div className="flex gap-3">
          <input
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="Pregunta algo o pide un reporte..."
            className="flex-1 rounded-xl border border-zinc-300 bg-white px-4 py-3 text-sm outline-none ring-zinc-900 focus:ring-2 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100"
            disabled={loading}
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="rounded-xl bg-zinc-900 px-5 py-3 text-sm font-medium text-white transition hover:bg-zinc-700 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-300"
          >
            Enviar
          </button>
        </div>
      </form>
    </div>
  );
}
