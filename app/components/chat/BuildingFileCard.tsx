"use client";

import { motion } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";
import type { BackgroundJobSnapshot } from "@/lib/types";

type BuildingFileCardProps = {
  job: BackgroundJobSnapshot;
  progress?: number;
  stage?: string;
  fileUrl?: string | null;
  error?: string | null;
};

export function BuildingFileCard({
  job,
  progress = job.progress ?? 0,
  stage = job.stage ?? "Preparando archivo...",
  fileUrl,
  error,
}: BuildingFileCardProps) {
  const { colors } = useTheme();
  const isDone = job.status === "SUCCEEDED" || Boolean(fileUrl);
  const isFailed = job.status === "FAILED" || Boolean(error);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="mt-3 overflow-hidden rounded-2xl border backdrop-blur-xl"
      style={{
        background: "rgba(255,255,255,0.06)",
        borderColor: isFailed ? `${colors.danger}55` : `${colors.accent}33`,
        boxShadow: `inset 0 1px 0 rgba(255,255,255,0.08), 0 12px 40px ${colors.glow}`,
      }}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        <motion.div
          animate={
            isDone
              ? { scale: [1, 1.08, 1], rotate: 0 }
              : isFailed
                ? { rotate: 0 }
                : { rotate: [0, 8, -8, 0] }
          }
          transition={{ duration: isDone ? 0.5 : 1.6, repeat: isDone || isFailed ? 0 : Infinity }}
          className="flex h-10 w-10 items-center justify-center rounded-xl text-lg"
          style={{
            background: isFailed ? `${colors.danger}22` : colors.accentSoft,
            border: `1px solid ${isFailed ? `${colors.danger}44` : `${colors.accent}33`}`,
          }}
        >
          {isFailed ? "!" : isDone ? "✓" : "📊"}
        </motion.div>

        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium" style={{ color: colors.text }}>
            {job.label}
          </p>
          <p className="truncate text-xs" style={{ color: colors.textSoft }}>
            {error ?? stage}
          </p>
        </div>

        <span
          className="rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-wide"
          style={{
            background: isFailed
              ? `${colors.danger}18`
              : isDone
                ? `${colors.success}18`
                : colors.accentSoft,
            color: isFailed ? colors.danger : isDone ? colors.success : colors.accent,
          }}
        >
          {isFailed ? "Error" : isDone ? "Listo" : job.status === "RUNNING" ? "Generando" : "En cola"}
        </span>
      </div>

      {!isDone && !isFailed ? (
        <div className="px-4 pb-3">
          <div
            className="h-1.5 overflow-hidden rounded-full"
            style={{ background: "rgba(255,255,255,0.08)" }}
          >
            <motion.div
              className="h-full rounded-full"
              style={{ background: `linear-gradient(90deg, ${colors.accent}, #38bdf8)` }}
              initial={{ width: "8%" }}
              animate={{ width: `${Math.max(progress, 8)}%` }}
              transition={{ duration: 0.45, ease: "easeOut" }}
            />
          </div>
        </div>
      ) : null}

      {fileUrl ? (
        <div className="border-t px-4 py-3" style={{ borderColor: colors.border }}>
          <a
            href={fileUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium transition hover:opacity-90"
            style={{
              background: `${colors.success}18`,
              color: colors.success,
              border: `1px solid ${colors.success}33`,
            }}
          >
            Descargar Excel
          </a>
        </div>
      ) : null}
    </motion.div>
  );
}
