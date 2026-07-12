"use client";

import { useEffect, useState } from "react";

type Project = {
  id: string;
  name: string;
  description: string | null;
  systemPrompt: string;
  tools: Array<{
    id: string;
    name: string;
    description: string;
    handlerKey: string;
  }>;
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/projects")
      .then((response) => response.json())
      .then((data) => setProjects(data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-zinc-50 px-6 py-10 dark:bg-black">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <p className="text-sm text-zinc-500">Configuración</p>
            <h1 className="text-3xl font-semibold text-zinc-900 dark:text-zinc-50">Proyectos</h1>
          </div>
          <a
            href="/chat"
            className="rounded-xl border border-zinc-300 px-4 py-2 text-sm dark:border-zinc-700"
          >
            Volver al chat
          </a>
        </div>

        {loading ? <p className="text-zinc-500">Cargando proyectos...</p> : null}

        <div className="space-y-4">
          {projects.map((project) => (
            <article
              key={project.id}
              className="rounded-2xl border border-zinc-200 bg-white p-6 dark:border-zinc-800 dark:bg-zinc-950"
            >
              <h2 className="text-xl font-semibold">{project.name}</h2>
              <p className="mt-2 text-sm text-zinc-500">{project.description}</p>

              <div className="mt-4">
                <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">System prompt</h3>
                <pre className="mt-2 overflow-x-auto rounded-xl bg-zinc-50 p-4 text-xs leading-6 text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
                  {project.systemPrompt}
                </pre>
              </div>

              <div className="mt-4">
                <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                  Herramientas ({project.tools.length})
                </h3>
                <div className="mt-2 space-y-2">
                  {project.tools.map((tool) => (
                    <div
                      key={tool.id}
                      className="rounded-xl border border-zinc-200 px-4 py-3 dark:border-zinc-800"
                    >
                      <p className="font-medium">{tool.name}</p>
                      <p className="text-sm text-zinc-500">{tool.description}</p>
                      <p className="mt-1 text-xs text-zinc-400">Handler: {tool.handlerKey}</p>
                    </div>
                  ))}
                </div>
              </div>
            </article>
          ))}
        </div>
      </div>
    </div>
  );
}
