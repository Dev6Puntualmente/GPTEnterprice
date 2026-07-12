"use client";

import { signOut, useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ChatWindow } from "@/app/components/ChatWindow";
import GlassButton from "@/app/components/ui/GlassButton";
import GlassCard from "@/app/components/ui/GlassCard";
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

export default function ChatPage() {
  const { data: session } = useSession();
  const { colors } = useTheme();
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
          style={{ color: colors.textSoft }}
        >
          Cargando...
        </motion.div>
      </div>
    );
  }

  const selectedProject = projects.find((p) => p.id === selectedProjectId);

  return (
    <div className="h-screen overflow-hidden p-3 md:p-5">
      <div className="mx-auto grid h-full max-w-7xl grid-cols-1 gap-4 overflow-hidden lg:grid-cols-[290px_1fr]">
        <GlassCard className="flex min-h-0 flex-col overflow-hidden p-4 md:p-5">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] uppercase tracking-[0.24em]" style={{ color: colors.textMuted }}>
                GPTEnterprice
              </p>
              <h1 className="text-xl font-semibold tracking-tight" style={{ color: colors.text }}>
                Agente interno
              </h1>
            </div>
            <ThemeToggle />
          </div>

          <label className="mb-2 block text-[11px] font-medium uppercase tracking-[0.18em]" style={{ color: colors.textMuted }}>
            Proyecto
          </label>
          <select
            value={selectedProjectId ?? ""}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            className="mb-4 w-full rounded-2xl border px-3 py-2.5 text-sm backdrop-blur-md outline-none"
            style={{
              borderColor: colors.border,
              background: "rgba(255,255,255,0.05)",
              color: colors.text,
            }}
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>

          {selectedProject ? (
            <div
              className="mb-4 rounded-2xl p-3 text-sm backdrop-blur-md"
              style={{
                background: "rgba(255,255,255,0.05)",
                color: colors.textSoft,
                border: `1px solid ${colors.border}`,
              }}
            >
              <p>{selectedProject.description}</p>
              <p className="mt-2 text-xs" style={{ color: colors.textMuted }}>
                {selectedProject.tools.length} herramientas activas
              </p>
            </div>
          ) : null}

          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium" style={{ color: colors.text }}>
              Conversaciones
            </h2>
            <GlassButton variant="soft" onClick={() => setSelectedConversationId(null)} className="px-3 py-1.5 text-xs">
              Nueva
            </GlassButton>
          </div>

          <div className="min-h-0 flex-1 space-y-1.5 overflow-y-auto overscroll-contain pr-1">
            {conversations.map((conversation) => {
              const active = selectedConversationId === conversation.id;
              return (
                <motion.button
                  key={conversation.id}
                  type="button"
                  whileHover={{ x: 2 }}
                  onClick={() => setSelectedConversationId(conversation.id)}
                  className="w-full rounded-2xl px-3 py-2.5 text-left text-sm transition backdrop-blur-md"
                  style={{
                    background: active ? colors.accentSoft : "rgba(255,255,255,0.03)",
                    color: active ? colors.accent : colors.textSoft,
                    border: `1px solid ${active ? `${colors.accent}33` : colors.border}`,
                  }}
                >
                  <span className="line-clamp-2">{conversation.title}</span>
                </motion.button>
              );
            })}
          </div>

          <div className="mt-4 space-y-2 border-t pt-4" style={{ borderColor: colors.border }}>
            <Link
              href="/settings/ai-servers"
              className="block rounded-xl px-2 py-1.5 text-sm transition hover:opacity-80"
              style={{ color: colors.accent }}
            >
              Proveedores de IA
            </Link>
            <Link
              href="/projects"
              className="block rounded-xl px-2 py-1.5 text-sm transition hover:opacity-80"
              style={{ color: colors.textSoft }}
            >
              Administrar proyectos
            </Link>
            <p className="truncate px-2 text-xs" style={{ color: colors.textMuted }}>
              Doc. {session?.user?.documentId}
            </p>
            <button
              type="button"
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="px-2 text-sm underline-offset-2 hover:underline"
              style={{ color: colors.textSoft }}
            >
              Cerrar sesión
            </button>
          </div>
        </GlassCard>

        <main className="flex min-h-0 flex-col overflow-hidden">
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
