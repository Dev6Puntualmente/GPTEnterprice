"use client";

import { motion } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";

type GlassButtonProps = {
  children: React.ReactNode;
  type?: "button" | "submit";
  variant?: "primary" | "ghost" | "soft" | "outline";
  size?: "sm" | "md";
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
};

export default function GlassButton({
  children,
  type = "button",
  variant = "primary",
  size = "md",
  disabled = false,
  onClick,
  className = "",
}: GlassButtonProps) {
  const { colors, mode } = useTheme();

  const sizeClass = size === "sm" ? "px-3 py-1.5 text-xs rounded-lg" : "px-4 py-2.5 text-sm rounded-xl";

  const styles =
    variant === "primary"
      ? {
          background:
            mode === "light"
              ? `linear-gradient(180deg, ${colors.accent} 0%, color-mix(in srgb, ${colors.accent} 88%, #3730a3) 100%)`
              : `linear-gradient(135deg, ${colors.accent}, color-mix(in srgb, ${colors.accent} 70%, #3b82f6))`,
          color: "#fff",
          border: mode === "light" ? "1px solid transparent" : "1px solid rgba(255,255,255,0.18)",
          boxShadow: disabled ? "none" : colors.shadowButton,
        }
      : variant === "soft"
        ? {
            background: colors.accentSoft,
            color: colors.accent,
            border: `1px solid color-mix(in srgb, ${colors.accent} 18%, transparent)`,
            boxShadow: "none",
          }
        : variant === "outline"
          ? {
              background: colors.surface,
              color: colors.text,
              border: `1px solid ${colors.borderStrong}`,
              boxShadow: mode === "light" ? "0 1px 2px rgba(15,23,42,0.04)" : "none",
            }
          : {
              background: "transparent",
              color: colors.textSoft,
              border: `1px solid ${colors.border}`,
              boxShadow: "none",
            };

  return (
    <motion.button
      type={type}
      disabled={disabled}
      onClick={onClick}
      whileHover={disabled ? undefined : { y: -1, scale: 1.01 }}
      whileTap={disabled ? undefined : { scale: 0.985 }}
      transition={{ type: "spring", stiffness: 500, damping: 34, mass: 0.55 }}
      className={`ui-smooth inline-flex items-center justify-center gap-1.5 font-medium disabled:cursor-not-allowed disabled:opacity-40 ${sizeClass} ${className}`}
      style={styles}
    >
      {children}
    </motion.button>
  );
}
