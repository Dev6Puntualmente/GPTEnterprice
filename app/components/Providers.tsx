"use client";

import { SessionProvider } from "next-auth/react";
import { ThemeProvider } from "@/app/components/theme/ThemeProvider";
import AppBackground from "@/app/components/ui/AppBackground";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <ThemeProvider>
        <AppBackground />
        {children}
      </ThemeProvider>
    </SessionProvider>
  );
}
