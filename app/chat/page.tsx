"use client";

import { useEffect, useState } from "react";
import { ChatWindow } from "@/app/components/ChatWindow";

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

  function handleNewConversation() {
    setSelectedConversationId(null);
  }

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
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-black">
        <p className="text-zinc-500">Cargando...</p>
      </div>
    );
  }

  if (!projects.length) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-zinc-50 px-6 dark:bg-black">
        <div className="max-w-md rounded-2xl border border-zinc-200 bg-white p-8 text-center dark:border-zinc-800 dark:bg-zinc-950">
          <h1 className="text-xl font-semibold">No hay proyectos</h1>
          <p className="mt-2 text-sm text-zinc-500">
            Ejecuta <code className="rounded bg-zinc-100 px-1 dark:bg-zinc-900">npm run db:seed</code>{" "}
            para crear el proyecto demo de RRHH.
          </p>
        </div>
      </div>
    );
  }

  const selectedProject = projects.find((project) => project.id === selectedProjectId);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-black">
      <div className="mx-auto grid min-h-screen max-w-7xl grid-cols-1 gap-4 p-4 lg:grid-cols-[280px_1fr]">
        <aside className="rounded-2xl border border-zinc-200 bg-white p-4 dark:border-zinc-800 dark:bg-zinc-950">
          <div className="mb-4">
            <p className="text-xs uppercase tracking-wide text-zinc-500">GPTEnterprice</p>
            <h1 className="text-xl font-semibold text-zinc-900 dark:text-zinc-50">Agente interno</h1>
          </div>

          <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-zinc-500">
            Proyecto
          </label>
          <select
            value={selectedProjectId ?? ""}
            onChange={(event) => setSelectedProjectId(event.target.value)}
            className="mb-4 w-full rounded-xl border border-zinc-300 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
          >
            {projects.map((project) => (
              <option key={project.id} value={project.id}>
                {project.name}
              </option>
            ))}
          </select>

          {selectedProject ? (
            <div className="mb-4 rounded-xl bg-zinc-50 p-3 text-sm text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300">
              <p>{selectedProject.description ?? "Sin descripción"}</p>
              <p className="mt-2 text-xs text-zinc-500">
                {selectedProject.tools.length} herramienta(s) activa(s)
              </p>
            </div>
          ) : null}

          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">Conversaciones</h2>
            <button
              type="button"
              onClick={handleNewConversation}
              className="rounded-lg bg-zinc-900 px-3 py-1.5 text-xs font-medium text-white dark:bg-zinc-100 dark:text-zinc-900"
            >
              Nueva
            </button>
          </div>

          <div className="space-y-2">
            {conversations.map((conversation) => (
              <button
                key={conversation.id}
                type="button"
                onClick={() => setSelectedConversationId(conversation.id)}
                className={`w-full rounded-xl px-3 py-2 text-left text-sm transition ${
                  selectedConversationId === conversation.id
                    ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900"
                    : "bg-zinc-50 text-zinc-700 hover:bg-zinc-100 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800"
                }`}
              >
                {conversation.title}
              </button>
            ))}
          </div>

          <a
            href="/projects"
            className="mt-6 block text-sm text-zinc-500 underline-offset-2 hover:underline"
          >
            Administrar proyectos
          </a>
        </aside>

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
