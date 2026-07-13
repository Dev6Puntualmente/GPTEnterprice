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
  index?: number;
  jobState?: {
    progress?: number;
    stage?: string;
    status?: BackgroundJobSnapshot["status"];
    fileUrl?: string | null;
    error?: string | null;
  };
};

const USER_BUBBLE_BG =
  "linear-gradient(135deg, #1e293b 0%, #0f172a 55%, #1e1b4b 100%)";

export function ChatMessageBubble({
  role,
  content,
  metadata,
  isStreaming = false,
  index = 0,
  jobState,
}: ChatMessageBubbleProps) {
  const { colors, mode } = useTheme();
  const isUser = role === "USER";
  const pendingJob = metadata?.pending_job;
  const files = metadata?.files ?? [];
  const fileUrl = jobState?.fileUrl ?? files[0] ?? null;
  const status = jobState?.status ?? metadata?.job_status ?? pendingJob?.status;
  const showJobCard = Boolean(pendingJob);

  return (
    <motion.div
      initial={{ opacity: 0, y: 14, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        type: "spring",
        stiffness: 380,
        damping: 30,
        delay: Math.min(index * 0.04, 0.2),
      }}
      className={`flex min-w-0 ${isUser ? "justify-end" : "justify-start"}`}
    >
      <motion.div
        layout
        className={`relative max-w-[min(88%,42rem)] min-w-0 break-words rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed sm:px-4 sm:py-3 ${
          isUser ? "rounded-br-md" : "rounded-bl-md"
        }`}
        style={
          isUser
            ? {
                background: USER_BUBBLE_BG,
                color: "#ffffff",
                boxShadow:
                  mode === "light"
                    ? "0 8px 28px rgba(15, 23, 42, 0.22), 0 0 0 1px rgba(255,255,255,0.06) inset"
                    : "0 12px 32px rgba(15, 23, 42, 0.45)",
              }
            : {
                background:
                  mode === "light"
                    ? "rgba(255,255,255,0.88)"
                    : colors.surface,
                color: colors.text,
                border: `1px solid ${colors.border}`,
                boxShadow:
                  mode === "light"
                    ? "0 4px 24px rgba(15,23,42,0.06), 0 1px 0 rgba(255,255,255,0.8) inset"
                    : `0 8px 32px ${colors.glow}`,
                backdropFilter: mode === "light" ? "blur(8px)" : undefined,
              }
        }
      >
        {!isUser && mode === "light" ? (
          <motion.div
            className="pointer-events-none absolute -left-px top-3 h-8 w-1 rounded-full"
            style={{ background: `linear-gradient(180deg, ${colors.accent}, transparent)` }}
            initial={{ scaleY: 0 }}
            animate={{ scaleY: 1 }}
            transition={{ delay: 0.1, duration: 0.35 }}
          />
        ) : null}

        <div className="relative">
          <Markdown content={content} inverted={isUser} />
          {isStreaming ? (
            <motion.span
              className="ml-0.5 inline-block h-3.5 w-0.5 align-middle"
              style={{ background: isUser ? "#c7d2fe" : colors.accent }}
              animate={{ opacity: [1, 0.15, 1], scaleY: [1, 0.6, 1] }}
              transition={{ duration: 0.75, repeat: Infinity }}
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
                <motion.div
                  key={url}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-3 max-w-full overflow-hidden rounded-xl"
                  style={{
                    border: `1px solid ${colors.border}`,
                    background: colors.surfaceMuted,
                  }}
                >
                  <img
                    src={url}
                    alt="Archivo generado"
                    className="max-h-[360px] w-full object-contain"
                  />
                  <a
                    href={url}
                    target="_blank"
                    rel="noreferrer"
                    className="block py-1.5 text-center text-xs font-medium transition-opacity hover:opacity-70"
                    style={{
                      color: colors.textSoft,
                      borderTop: `1px solid ${colors.border}`,
                    }}
                  >
                    Abrir en nueva pestaña
                  </a>
                </motion.div>
              );
            }
            return (
              <a
                key={url}
                href={url}
                target="_blank"
                rel="noreferrer"
                className="mt-3 inline-flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium"
                style={{
                  background: `${colors.success}12`,
                  color: colors.success,
                  border: `1px solid ${colors.success}30`,
                }}
              >
                Descargar archivo
              </a>
            );
          })}

        {metadata?.model_used ? (
          <p
            className="mt-1.5 text-[10px] tabular-nums"
            style={{ color: isUser ? "rgba(255,255,255,0.55)" : colors.textMuted }}
          >
            {metadata.model_used}
          </p>
        ) : null}
      </motion.div>
    </motion.div>
  );
}
