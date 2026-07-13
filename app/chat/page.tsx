"use client";

import { signOut, useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ChatWindow } from "@/app/components/ChatWindow";
import GlassButton from "@/app/components/ui/GlassButton";
import ThemeToggle from "@/app/components/theme/ThemeToggle";
import { useTheme } from "@/app/components/theme/ThemeProvider";

type Project = {
  id: string;
  name: string;
  description: string | null;
  tools: Array<{ name: string; description: string }>;
};

type Conversation = {
  id: string;
  title: string;
  updatedAt: string;
};

function formatRelativeDate(iso: string) {
  try {
    const date = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));
    if (days === 0) return "Hoy";
    if (days === 1) return "Ayer";
    if (days < 7) return `${days}d`;
    return date.toLocaleDateString("es", { day: "numeric", month: "short" });
  } catch {
    return "";
  }
}

export default function ChatPage() {
  const { data: session } = useSession();
  const { colors, mode } = useTheme();
  const [projects, setProjects] = useState<Project[]>([]);
  const [selectedProjectId, setSelectedProjectId] = useState<string | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversationId, setSelectedConversationId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/projects")
      .then((response) => response.json())
      .then((data: Project[]) => {
        setProjects(data);
        if (data[0]) setSelectedProjectId(data[0].id);
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedProjectId) return;
    fetch(`/api/conversations?projectId=${selectedProjectId}`)
      .then((response) => response.json())
      .then((data: Conversation[]) => {
        setConversations(data);
        setSelectedConversationId(data[0]?.id ?? null);
      });
  }, [selectedProjectId]);

  function handleConversationCreated(conversationId: string) {
    setSelectedConversationId(conversationId);
    if (selectedProjectId) {
      fetch(`/api/conversations?projectId=${selectedProjectId}`)
        .then((response) => response.json())
        .then((data: Conversation[]) => setConversations(data));
    }
  }

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <motion.div
          animate={{ opacity: [0.4, 1, 0.4] }}
          transition={{ duration: 1.4, repeat: Infinity }}
          style={{ color: colors.textMuted }}
          className="text-sm"
        >
          Cargando...
        </motion.div>
      </div>
    );
  }

  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  return (
    <div className="h-screen overflow-x-hidden overflow-y-hidden p-2 sm:p-4">
      <div className="mx-auto grid h-full max-w-[1400px] grid-cols-1 gap-3 overflow-hidden lg:grid-cols-[272px_1fr]">
        {/* Sidebar */}
        <aside
          className="flex min-h-0 flex-col overflow-hidden rounded-2xl border"
          style={{
            background: colors.panel,
            borderColor: colors.border,
            boxShadow: colors.shadow,
          }}
        >
          {/* Brand */}
          <div
            className="flex items-center justify-between gap-2 border-b px-4 py-4"
            style={{ borderColor: colors.border }}
          >
            <div className="flex items-center gap-2.5">
              <div
                className="flex h-8 w-8 items-center justify-center rounded-lg text-xs font-bold text-white"
                style={{
                  background: `linear-gradient(135deg, ${colors.accent}, color-mix(in srgb, ${colors.accent} 70%, #3b82f6))`,
                }}
              >
                G
              </div>
              <div>
                <p className="text-sm font-semibold leading-tight" style={{ color: colors.text }}>
                  GPTEnterprice
                </p>
                <p className="text-[11px]" style={{ color: colors.textMuted }}>
                  Agente interno
                </p>
              </div>
            </div>
            <ThemeToggle />
          </div>

          {/* Project */}
          <div className="border-b px-3 py-3" style={{ borderColor: colors.border }}>
            <label
              className="mb-1.5 block text-[10px] font-semibold uppercase tracking-wider"
              style={{ color: colors.textMuted }}
            >
              Proyecto
            </label>
            <select
              value={selectedProjectId ?? ""}
              onChange={(e) => setSelectedProjectId(e.target.value)}
              className="w-full rounded-lg border px-3 py-2 text-sm outline-none transition focus:ring-2"
              style={{
                borderColor: colors.borderStrong,
                background: colors.input,
                color: colors.text,
                boxShadow: mode === "light" ? "0 1px 2px rgba(15,23,42,0.04)" : "none",
              }}
            >
              {projects.map((project) => (
                <option key={project.id} value={project.id}>
                  {project.name}
                </option>
              ))}
            </select>
            {selectedProject ? (
              <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed" style={{ color: colors.textMuted }}>
                {selectedProject.description}
              </p>
            ) : null}
          </div>

          {/* Conversations header */}
          <div className="flex items-center justify-between px-3 pb-2 pt-3">
            <span className="text-[10px] font-semibold uppercase tracking-wider" style={{ color: colors.textMuted }}>
              Chats
            </span>
            <GlassButton
              variant="soft"
              size="sm"
              onClick={() => setSelectedConversationId(null)}
              className="!rounded-md"
            >
              + Nuevo
            </GlassButton>
          </div>

          {/* Conversation list */}
          <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto overscroll-contain px-2 pb-2">
            {conversations.length === 0 ? (
              <p className="px-2 py-6 text-center text-xs" style={{ color: colors.textMuted }}>
                Sin conversaciones aún
              </p>
            ) : (
              conversations.map((conversation) => {
                const active = selectedConversationId === conversation.id;
                return (
                  <motion.button
                    key={conversation.id}
                    type="button"
                    onClick={() => setSelectedConversationId(conversation.id)}
                    whileHover={{ x: 2 }}
                    transition={{ type: "spring", stiffness: 420, damping: 32, mass: 0.6 }}
                    className="ui-smooth group relative w-full min-w-0 rounded-lg px-2.5 py-2 text-left"
                    style={{
                      background: active ? colors.accentSoft : "transparent",
                      color: active ? colors.text : colors.textSoft,
                    }}
                  >
                    {active ? (
                      <span
                        className="absolute bottom-2 left-0 top-2 w-0.5 rounded-full"
                        style={{ background: colors.accent }}
                      />
                    ) : null}
                    <div className="flex items-start justify-between gap-2 pl-1">
                      <span className="line-clamp-2 text-[13px] font-medium leading-snug">
                        {conversation.title || "Sin título"}
                      </span>
                      <span
                        className="shrink-0 text-[10px] tabular-nums"
                        style={{ color: colors.textMuted }}
                      >
                        {formatRelativeDate(conversation.updatedAt)}
                      </span>
                    </div>
                  </motion.button>
                );
              })
            )}
          </div>

          {/* Footer nav */}
          <div
            className="shrink-0 space-y-0.5 border-t px-2 py-3"
            style={{ borderColor: colors.border, background: colors.surfaceMuted }}
          >
            <Link
              href="/settings/ai-servers"
              className="ui-smooth flex items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] font-medium hover:bg-black/[0.03] dark:hover:bg-white/[0.04]"
              style={{ color: colors.textSoft }}
            >
              <span style={{ color: colors.accent }}>◆</span>
              Proveedores IA
            </Link>
            <Link
              href="/projects"
              className="ui-smooth flex items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] hover:bg-black/[0.03] dark:hover:bg-white/[0.04]"
              style={{ color: colors.textMuted }}
            >
              <span>◇</span>
              Proyectos
            </Link>
            <div className="flex items-center justify-between px-2.5 pt-2">
              <p className="truncate text-[11px]" style={{ color: colors.textMuted }}>
                {session?.user?.documentId}
              </p>
              <button
                type="button"
                onClick={() => signOut({ callbackUrl: "/login" })}
                className="text-[11px] font-medium transition hover:opacity-70"
                style={{ color: colors.textMuted }}
              >
                Salir
              </button>
            </div>
          </div>
        </aside>

        <main className="flex min-h-0 min-w-0 flex-col overflow-hidden">
          {selectedProjectId ? (
            <ChatWindow
              conversationId={selectedConversationId}
              projectId={selectedProjectId}
              onConversationCreated={handleConversationCreated}
            />
          ) : null}
        </main>
      </div>
    </div>
  );
}
