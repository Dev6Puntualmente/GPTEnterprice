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
      className={`rounded-2xl border backdrop-blur-xl ${className}`}
      style={{
        background: colors.panel,
        borderColor: colors.border,
        boxShadow: `0 20px 60px ${colors.glow}`,
      }}
      {...props}
    >
      {children}
    </motion.div>
  );
}
