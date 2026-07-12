"use client";

import { motion } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";

export default function ThemeToggle() {
  const { mode, toggleTheme, colors } = useTheme();

  return (
    <motion.button
      type="button"
      onClick={toggleTheme}
      whileHover={{ scale: 1.05 }}
      whileTap={{ scale: 0.95 }}
      className="relative flex h-10 w-10 items-center justify-center rounded-xl border backdrop-blur-md"
      style={{
        borderColor: colors.border,
        background: colors.panel,
        color: colors.text,
      }}
      aria-label={mode === "dark" ? "Activar modo claro" : "Activar modo oscuro"}
    >
      <motion.span
        key={mode}
        initial={{ rotate: -90, opacity: 0, scale: 0.5 }}
        animate={{ rotate: 0, opacity: 1, scale: 1 }}
        transition={{ type: "spring", stiffness: 260, damping: 20 }}
        className="text-lg"
      >
        {mode === "dark" ? "☀️" : "🌙"}
      </motion.span>
    </motion.button>
  );
}
