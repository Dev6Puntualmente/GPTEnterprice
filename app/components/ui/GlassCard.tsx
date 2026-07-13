"use client";

import { motion, type HTMLMotionProps } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";

type GlassCardProps = HTMLMotionProps<"div"> & {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  flat?: boolean;
};

export default function GlassCard({
  children,
  className = "",
  hover = false,
  flat = false,
  ...props
}: GlassCardProps) {
  const { colors } = useTheme();

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ type: "spring", stiffness: 280, damping: 28 }}
      whileHover={hover ? { y: -1 } : undefined}
      className={`rounded-2xl border ${flat ? "" : "backdrop-blur-xl"} ${className}`}
      style={{
        background: colors.panel,
        borderColor: colors.border,
        boxShadow: flat ? "none" : colors.shadow,
      }}
      {...props}
    >
      {children}
    </motion.div>
  );
}
