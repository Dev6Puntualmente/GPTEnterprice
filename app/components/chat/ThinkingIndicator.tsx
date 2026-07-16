"use client";

import { motion } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";

type ThinkingIndicatorProps = {
  label: string;
  presentation?: boolean;
};

export function ThinkingIndicator({ label, presentation = false }: ThinkingIndicatorProps) {
  const { colors, mode } = useTheme();

  return (
    <div className="flex justify-start">
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        className="relative flex max-w-md items-center gap-3 overflow-hidden rounded-2xl rounded-bl-md px-4 py-3 text-sm"
        style={{
          color: colors.text,
          border: `1px solid ${colors.border}`,
          background:
            mode === "light" ? "rgba(255,255,255,0.62)" : "rgba(15,23,42,0.55)",
          boxShadow:
            mode === "light"
              ? "0 10px 36px rgba(99,102,241,0.1)"
              : `0 14px 42px ${colors.glow}`,
        }}
      >
        <span className="pointer-events-none absolute inset-0 backdrop-blur-xl" aria-hidden />
        <motion.span
          className="pointer-events-none absolute -left-1/3 top-0 h-full w-1/2 opacity-50"
          style={{
            background: `linear-gradient(90deg, transparent, ${colors.accent}22, transparent)`,
          }}
          animate={{ x: ["-30%", "220%"] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
        />

        <div
          className="relative flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-base backdrop-blur-md"
          style={{
            background: `${colors.accent}16`,
            border: `1px solid ${colors.accent}30`,
          }}
        >
          {presentation ? (
            <motion.span
              animate={{ scale: [1, 1.08, 1], rotate: [0, 2, -2, 0] }}
              transition={{ duration: 2.4, repeat: Infinity }}
            >
              📊
            </motion.span>
          ) : (
            <motion.span
              className="flex gap-0.5"
              aria-hidden
            >
              {[0, 1, 2].map((dot) => (
                <motion.span
                  key={dot}
                  className="inline-block h-1.5 w-1.5 rounded-full"
                  style={{ background: colors.accent }}
                  animate={{ y: [0, -5, 0], opacity: [0.35, 1, 0.35] }}
                  transition={{ duration: 0.85, repeat: Infinity, delay: dot * 0.14 }}
                />
              ))}
            </motion.span>
          )}
        </div>

        <div className="relative min-w-0 flex-1">
          <p className="truncate font-medium" style={{ color: colors.text }}>
            {label}
          </p>
          {presentation ? (
            <p className="mt-0.5 text-xs" style={{ color: colors.textMuted }}>
              Presenton + vLLM · no cierres esta pestaña
            </p>
          ) : null}
        </div>

        {presentation ? (
          <motion.div
            className="relative h-8 w-8 shrink-0"
            aria-hidden
          >
            <svg viewBox="0 0 36 36" className="h-8 w-8 -rotate-90">
              <circle
                cx="18"
                cy="18"
                r="14"
                fill="none"
                stroke={colors.border}
                strokeWidth="3"
              />
              <motion.circle
                cx="18"
                cy="18"
                r="14"
                fill="none"
                stroke={colors.accent}
                strokeWidth="3"
                strokeLinecap="round"
                strokeDasharray="88"
                animate={{ strokeDashoffset: [88, 18, 88] }}
                transition={{ duration: 3.5, repeat: Infinity, ease: "easeInOut" }}
              />
            </svg>
          </motion.div>
        ) : null}
      </motion.div>
    </div>
  );
}
