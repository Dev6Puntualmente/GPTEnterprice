"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";

type GlassCardProps = HTMLMotionProps<"div"> & {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
};

export default function GlassCard({
  children,
  className = "",
  hover = false,
  ...props
}: GlassCardProps) {
  const { colors } = useTheme();

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 260, damping: 24 }}
      whileHover={hover ? { y: -2, scale: 1.005 } : undefined}
      className={`rounded-[1.35rem] border backdrop-blur-2xl ${className}`}
      style={{
        background: colors.panel,
        borderColor: colors.border,
        boxShadow: `0 24px 80px ${colors.glow}, inset 0 1px 0 rgba(255,255,255,0.08)`,
      }}
      {...props}
    >
      {children}
    </motion.div>
  );
}
