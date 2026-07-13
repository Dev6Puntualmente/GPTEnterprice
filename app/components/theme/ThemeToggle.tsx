"use client";

import { motion } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";

export default function ThemeToggle() {
  const { mode, toggleTheme, colors } = useTheme();
  const isDark = mode === "dark";

  return (
    <motion.button
      type="button"
      onClick={toggleTheme}
      whileHover={{ scale: 1.04 }}
      whileTap={{ scale: 0.96 }}
      className="relative flex h-9 w-9 items-center justify-center rounded-lg border transition-colors"
      style={{
        borderColor: colors.border,
        background: colors.surfaceMuted,
        color: colors.textSoft,
      }}
      aria-label={isDark ? "Activar modo claro" : "Activar modo oscuro"}
    >
      <motion.svg
        key={mode}
        initial={{ rotate: -40, opacity: 0, scale: 0.8 }}
        animate={{ rotate: 0, opacity: 1, scale: 1 }}
        transition={{ type: "spring", stiffness: 320, damping: 22 }}
        width="16"
        height="16"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {isDark ? (
          <>
            <circle cx="12" cy="12" r="4" />
            <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
          </>
        ) : (
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        )}
      </motion.svg>
    </motion.button>
  );
}
