"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import GlassCard from "@/app/components/ui/GlassCard";
import ThemeToggle from "@/app/components/theme/ThemeToggle";
import { useTheme } from "@/app/components/theme/ThemeProvider";

type Project = {
  id: string;
  name: string;
  description: string | null;
  systemPrompt: string;
  tools: Array<{ id: string; name: string; description: string; handlerKey: string }>;
};

export default function ProjectsPage() {
  const { colors } = useTheme();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/projects")
      .then((response) => response.json())
      .then((data) => setProjects(data))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen px-6 py-10">
      <div className="mx-auto max-w-4xl">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <p className="text-sm" style={{ color: colors.textSoft }}>
              Configuración
            </p>
            <h1 className="text-3xl font-bold" style={{ color: colors.text }}>
              Proyectos
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link
              href="/chat"
              className="rounded-xl border px-4 py-2 text-sm backdrop-blur-md"
              style={{ borderColor: colors.border, color: colors.textSoft }}
            >
              Volver al chat
            </Link>
          </div>
        </div>

        {loading ? (
          <p style={{ color: colors.textSoft }}>Cargando proyectos...</p>
        ) : (
          <div className="space-y-4">
            {projects.map((project, index) => (
              <GlassCard key={project.id} hover className="p-6">
                <motion.div
                  initial={{ opacity: 0, y: 14 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                >
                  <h2 className="text-xl font-semibold" style={{ color: colors.text }}>
                    {project.name}
                  </h2>
                  <p className="mt-2 text-sm" style={{ color: colors.textSoft }}>
                    {project.description}
                  </p>

                  <div className="mt-4">
                    <h3 className="text-sm font-medium" style={{ color: colors.textSoft }}>
                      Herramientas ({project.tools.length})
                    </h3>
                    <div className="mt-2 space-y-2">
                      {project.tools.map((tool) => (
                        <div
                          key={tool.id}
                          className="rounded-xl border px-4 py-3 backdrop-blur-sm"
                          style={{ borderColor: colors.border, background: colors.panelAlt }}
                        >
                          <p className="font-medium" style={{ color: colors.text }}>
                            {tool.name}
                          </p>
                          <p className="text-sm" style={{ color: colors.textSoft }}>
                            {tool.description}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                </motion.div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
