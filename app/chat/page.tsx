"use client";

import { signOut, useSession } from "next-auth/react";
import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { ChatWindow } from "@/app/components/ChatWindow";
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
      <div className="flex min-h-screen items-center justify-center">
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
    <div className="min-h-screen p-4 md:p-6">
      <div className="mx-auto grid min-h-[calc(100vh-3rem)] max-w-7xl grid-cols-1 gap-4 lg:grid-cols-[300px_1fr]">
        <GlassCard className="flex flex-col p-4">
          <div className="mb-4 flex items-start justify-between">
            <div>
              <p className="text-[10px] uppercase tracking-[0.2em]" style={{ color: colors.textMuted }}>
                GPTEnterprice
              </p>
              <h1 className="text-lg font-bold" style={{ color: colors.text }}>
                Agente interno
              </h1>
            </div>
            <ThemeToggle />
          </div>

          <label className="mb-1 block text-xs font-medium uppercase tracking-wide" style={{ color: colors.textMuted }}>
            Proyecto
          </label>
          <select
            value={selectedProjectId ?? ""}
            onChange={(e) => setSelectedProjectId(e.target.value)}
            className="mb-3 w-full rounded-xl border px-3 py-2 text-sm backdrop-blur-md"
            style={{ borderColor: colors.border, background: colors.panelAlt, color: colors.text }}
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>

          {selectedProject ? (
            <div className="mb-4 rounded-xl p-3 text-sm" style={{ background: colors.panelAlt, color: colors.textSoft }}>
              <p>{selectedProject.description}</p>
              <p className="mt-1 text-xs" style={{ color: colors.textMuted }}>
                {selectedProject.tools.length} tool(s)
              </p>
            </div>
          ) : null}

          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-sm font-medium" style={{ color: colors.text }}>
              Conversaciones
            </h2>
            <motion.button
              whileTap={{ scale: 0.95 }}
              type="button"
              onClick={() => setSelectedConversationId(null)}
              className="rounded-lg px-3 py-1 text-xs font-medium text-white"
              style={{ background: colors.accent }}
            >
              Nueva
            </motion.button>
          </div>

          <div className="flex-1 space-y-1.5 overflow-y-auto">
            {conversations.map((conversation) => (
              <motion.button
                key={conversation.id}
                type="button"
                whileHover={{ x: 2 }}
                onClick={() => setSelectedConversationId(conversation.id)}
                className="w-full rounded-xl px-3 py-2 text-left text-sm transition"
                style={{
                  background:
                    selectedConversationId === conversation.id ? colors.accentSoft : "transparent",
                  color: selectedConversationId === conversation.id ? colors.accent : colors.textSoft,
                  border: `1px solid ${selectedConversationId === conversation.id ? `${colors.accent}40` : "transparent"}`,
                }}
              >
                {conversation.title}
              </motion.button>
            ))}
          </div>

          <div className="mt-4 space-y-2 border-t pt-4" style={{ borderColor: colors.border }}>
            <Link
              href="/settings/ai-servers"
              className="block text-sm transition hover:opacity-80"
              style={{ color: colors.accent }}
            >
              ⚙️ Proveedores de IA
            </Link>
            <Link href="/projects" className="block text-sm" style={{ color: colors.textSoft }}>
              Administrar proyectos
            </Link>
            <p className="truncate text-xs" style={{ color: colors.textMuted }}>
              Doc. {session?.user?.documentId}
            </p>
            <button
              type="button"
              onClick={() => signOut({ callbackUrl: "/login" })}
              className="text-sm underline-offset-2 hover:underline"
              style={{ color: colors.textSoft }}
            >
              Cerrar sesión
            </button>
          </div>
        </GlassCard>

        <main className="min-h-[70vh]">
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
