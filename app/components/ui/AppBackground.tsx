"use client";

import { motion } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";

export default function AppBackground() {
  const { colors } = useTheme();

  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute inset-0" style={{ background: colors.bg }} />

      <motion.div
        className="absolute -left-24 top-0 h-[420px] w-[420px] rounded-full blur-3xl"
        style={{ background: colors.orb1 }}
        animate={{ x: [0, 40, 0], y: [0, 30, 0], scale: [1, 1.08, 1] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute right-0 top-1/4 h-[360px] w-[360px] rounded-full blur-3xl"
        style={{ background: colors.orb2 }}
        animate={{ x: [0, -30, 0], y: [0, 40, 0], scale: [1, 1.12, 1] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-0 left-1/3 h-[320px] w-[320px] rounded-full blur-3xl"
        style={{ background: colors.orb3 }}
        animate={{ x: [0, 25, 0], y: [0, -20, 0], scale: [1, 1.06, 1] }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />

      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage: `
            linear-gradient(${colors.text} 1px, transparent 1px),
            linear-gradient(90deg, ${colors.text} 1px, transparent 1px)
          `,
          backgroundSize: "48px 48px",
        }}
      />
    </div>
  );
}
