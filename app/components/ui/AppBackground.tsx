"use client";

import { motion } from "framer-motion";
import { useTheme } from "@/app/components/theme/ThemeProvider";
import ParticleField from "@/app/components/ui/ParticleField";

export default function AppBackground() {
  const { colors, mode } = useTheme();

  return (
    <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <motion.div
        className="absolute inset-0"
        animate={{
          background:
            mode === "light"
              ? [
                  `linear-gradient(165deg, ${colors.bg} 0%, ${colors.bgAlt} 45%, #e8ecff 100%)`,
                  `linear-gradient(165deg, #eef1ff 0%, ${colors.bgAlt} 50%, ${colors.bg} 100%)`,
                  `linear-gradient(165deg, ${colors.bg} 0%, ${colors.bgAlt} 45%, #e8ecff 100%)`,
                ]
              : colors.bg,
        }}
        transition={{ duration: 18, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.div
        className="absolute -left-24 top-0 h-[420px] w-[420px] rounded-full blur-3xl"
        style={{ background: colors.orb1 }}
        animate={{ x: [0, 40, 10, 0], y: [0, 24, 8, 0], scale: [1, 1.08, 1] }}
        transition={{ duration: 14, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute right-0 top-1/4 h-[340px] w-[340px] rounded-full blur-3xl"
        style={{ background: colors.orb2 }}
        animate={{ x: [0, -28, -8, 0], y: [0, 36, 12, 0], scale: [1, 1.05, 1] }}
        transition={{ duration: 16, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="absolute bottom-0 left-1/3 h-[280px] w-[280px] rounded-full blur-3xl"
        style={{ background: colors.orb3 }}
        animate={{ x: [0, 20, -10, 0], y: [0, -16, 6, 0] }}
        transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
      />

      <ParticleField density={mode === "light" ? 42 : 56} particleScale={1.45} />

      {mode === "light" ? (
        <div
          className="absolute inset-0 opacity-[0.22]"
          style={{
            backgroundImage: `radial-gradient(circle at 1px 1px, ${colors.borderStrong} 1px, transparent 0)`,
            backgroundSize: "28px 28px",
          }}
        />
      ) : (
        <div
          className="absolute inset-0 opacity-[0.04]"
          style={{
            backgroundImage: `
              linear-gradient(${colors.text} 1px, transparent 1px),
              linear-gradient(90deg, ${colors.text} 1px, transparent 1px)
            `,
            backgroundSize: "48px 48px",
          }}
        />
      )}
    </div>
  );
}
