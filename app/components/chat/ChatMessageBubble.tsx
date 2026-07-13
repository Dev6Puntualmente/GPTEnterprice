"use client";

import { motion } from "framer-motion";
import { BuildingFileCard } from "@/app/components/chat/BuildingFileCard";
import { useTheme } from "@/app/components/theme/ThemeProvider";
import { Markdown } from "@/app/components/chat/Markdown";
import type { BackgroundJobSnapshot, MessageMetadata } from "@/lib/types";

type ChatMessageBubbleProps = {
  role: "USER" | "ASSISTANT";
  content: string;
  metadata?: MessageMetadata | null;
  isStreaming?: boolean;
  jobState?: {
    progress?: number;
    stage?: string;
    status?: BackgroundJobSnapshot["status"];
    fileUrl?: string | null;
    error?: string | null;
  };
};

export function ChatMessageBubble({
  role,
  content,
  metadata,
  isStreaming = false,
  jobState,
}: ChatMessageBubbleProps) {
  const { colors } = useTheme();
  const isUser = role === "USER";
  const pendingJob = metadata?.pending_job;
  const files = metadata?.files ?? [];
  const fileUrl = jobState?.fileUrl ?? files[0] ?? null;
  const status = jobState?.status ?? metadata?.job_status ?? pendingJob?.status;
  const showJobCard = Boolean(pendingJob);

  return (
    <motion.div
      initial={{ opacity: 0, y: 12, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ type: "spring", stiffness: 320, damping: 28 }}
      className={`flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[88%] rounded-3xl px-4 py-3 text-sm leading-6 backdrop-blur-xl ${
          isUser ? "rounded-br-lg" : "rounded-bl-lg"
        }`}
        style={
          isUser
            ? {
                background: `linear-gradient(135deg, ${colors.accent}, color-mix(in srgb, ${colors.accent} 65%, #2563eb))`,
                color: "#fff",
                boxShadow: `0 12px 32px ${colors.glow}`,
                border: "1px solid rgba(255,255,255,0.14)",
              }
            : {
                background: "rgba(255,255,255,0.06)",
                color: colors.text,
                border: `1px solid ${colors.border}`,
                boxShadow: "inset 0 1px 0 rgba(255,255,255,0.06)",
              }
        }
      >
        <div className="relative">
          <Markdown content={content} />
          {isStreaming ? (
            <motion.span
              className="ml-0.5 inline-block h-4 w-0.5 align-middle"
              style={{ background: colors.accent }}
              animate={{ opacity: [1, 0.2, 1] }}
              transition={{ duration: 0.8, repeat: Infinity }}
            />
          ) : null}
        </div>

        {showJobCard && pendingJob ? (
          <BuildingFileCard
            job={{
              id: pendingJob.id,
              tool: pendingJob.tool,
              label: pendingJob.label,
              status: status ?? pendingJob.status,
              progress: jobState?.progress ?? metadata?.job_progress,
              stage: jobState?.stage ?? metadata?.job_stage,
            }}
            progress={jobState?.progress ?? metadata?.job_progress}
            stage={jobState?.stage ?? metadata?.job_stage}
            fileUrl={fileUrl}
            error={jobState?.error ?? null}
          />
        ) : null}

        {!pendingJob &&
          files.map((url) => {
            const isImage = /\.(svg|png|jpe?g|gif|webp)$/i.test(url);
            if (isImage) {
              return (
                <div key={url} className="mt-3 overflow-hidden rounded-2xl border border-white/10 shadow-lg max-w-full bg-white/5">
                  <img
                    src={url}
                    alt="Archivo Generado"
                    className="w-full max-h-[320px] object-contain"
                  />
                  <a
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="block text-center py-1.5 text-xs font-medium hover:bg-white/10 border-t border-white/10 transition-colors"
                    style={{ color: colors.textSoft }}
                  >
                    Abrir en nueva pestaña
                  </a>
                </div>
              );
            }
            return (
              <a
                key={url}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium"
                style={{
                  background: `${colors.success}18`,
                  color: colors.success,
                  border: `1px solid ${colors.success}33`,
                }}
              >
                Descargar Excel
              </a>
            );
          })}

        {metadata?.model_used ? (
          <p className="mt-2 text-[10px] opacity-50">{metadata.model_used}</p>
        ) : null}
      </div>
    </motion.div>
  );
}
