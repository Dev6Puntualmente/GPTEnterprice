"use client";

import { motion } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";

type GlassButtonProps = {
  children: React.ReactNode;
  type?: "button" | "submit";
  variant?: "primary" | "ghost" | "soft";
  disabled?: boolean;
  onClick?: () => void;
  className?: string;
};

export default function GlassButton({
  children,
  type = "button",
  variant = "primary",
  disabled = false,
  onClick,
  className = "",
}: GlassButtonProps) {
  const { colors } = useTheme();

  const styles =
    variant === "primary"
      ? {
          background: `linear-gradient(135deg, ${colors.accent}, color-mix(in srgb, ${colors.accent} 70%, #3b82f6))`,
          color: "#fff",
          border: "1px solid rgba(255,255,255,0.18)",
          boxShadow: `0 10px 30px ${colors.glow}`,
        }
      : variant === "soft"
        ? {
            background: colors.accentSoft,
            color: colors.accent,
            border: `1px solid color-mix(in srgb, ${colors.accent} 25%, transparent)`,
          }
        : {
            background: "transparent",
            color: colors.textSoft,
            border: `1px solid ${colors.border}`,
          };

  return (
    <motion.button
      type={type}
      disabled={disabled}
      onClick={onClick}
      whileHover={disabled ? undefined : { y: -1, scale: 1.02 }}
      whileTap={disabled ? undefined : { scale: 0.98 }}
      className={`rounded-xl px-4 py-2.5 text-sm font-medium backdrop-blur-md transition disabled:cursor-not-allowed disabled:opacity-45 ${className}`}
      style={styles}
    >
      {children}
    </motion.button>
  );
}
