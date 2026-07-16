"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";
import {
  downloadFilenameFromUrl,
  fileKindFromName,
  normalizeDownloadUrl,
} from "@/lib/download-url";

type DownloadFileButtonProps = {
  url: string;
  label?: string;
};

const KIND_LABEL: Record<ReturnType<typeof fileKindFromName>, string> = {
  pdf: "Descargar PDF",
  pptx: "Descargar presentación",
  xlsx: "Descargar Excel",
  image: "Descargar imagen",
  other: "Descargar archivo",
};

const KIND_ICON: Record<ReturnType<typeof fileKindFromName>, string> = {
  pdf: "📄",
  pptx: "📊",
  xlsx: "📈",
  image: "🖼️",
  other: "⬇️",
};

export function DownloadFileButton({ url, label }: DownloadFileButtonProps) {
  const { colors, mode } = useTheme();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const href = normalizeDownloadUrl(url);
  const filename = downloadFilenameFromUrl(href);
  const kind = fileKindFromName(filename);
  const text = label ?? KIND_LABEL[kind];

  async function handleDownload() {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(href, { credentials: "same-origin" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = filename;
      anchor.rel = "noopener";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(objectUrl);
    } catch {
      setError("No se pudo descargar. Intenta de nuevo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mt-3 flex flex-col gap-1.5">
      <motion.button
        type="button"
        onClick={() => void handleDownload()}
        disabled={busy}
        whileHover={{ scale: busy ? 1 : 1.02 }}
        whileTap={{ scale: busy ? 1 : 0.98 }}
        className="group relative inline-flex w-full max-w-sm items-center justify-center gap-2.5 overflow-hidden rounded-2xl px-4 py-3 text-sm font-semibold transition disabled:opacity-70 sm:w-auto"
        style={{
          color: colors.text,
          border: `1px solid ${colors.border}`,
          background:
            mode === "light"
              ? "rgba(255,255,255,0.55)"
              : "rgba(15,23,42,0.45)",
          boxShadow:
            mode === "light"
              ? "0 8px 32px rgba(99,102,241,0.12)"
              : `0 12px 40px ${colors.glow}`,
        }}
      >
        <span
          className="pointer-events-none absolute inset-0 backdrop-blur-xl"
          aria-hidden
        />
        <motion.span
          className="pointer-events-none absolute inset-0 opacity-60"
          style={{
            background: `linear-gradient(135deg, ${colors.accentSoft}, transparent 55%, ${colors.accent}22)`,
          }}
          animate={{ opacity: busy ? [0.35, 0.7, 0.35] : 0.55 }}
          transition={{ duration: busy ? 1.4 : 0.3, repeat: busy ? Infinity : 0 }}
        />
        <span className="relative flex h-9 w-9 items-center justify-center rounded-xl text-lg backdrop-blur-md"
          style={{
            background: `${colors.accent}18`,
            border: `1px solid ${colors.accent}33`,
          }}
        >
          {busy ? (
            <motion.span
              className="inline-block h-4 w-4 rounded-full border-2 border-t-transparent"
              style={{ borderColor: `${colors.accent}55`, borderTopColor: "transparent" }}
              animate={{ rotate: 360 }}
              transition={{ duration: 0.8, repeat: Infinity, ease: "linear" }}
            />
          ) : (
            KIND_ICON[kind]
          )}
        </span>
        <span className="relative">{busy ? "Preparando descarga..." : text}</span>
      </motion.button>
      {error ? (
        <p className="text-xs" style={{ color: colors.danger }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
