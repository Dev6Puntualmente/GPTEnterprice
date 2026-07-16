"use client";

import { SessionProvider } from "next-auth/react";
import { ThemeProvider } from "@/app/components/theme/ThemeProvider";
import AppBackground from "@/app/components/ui/AppBackground";
import SessionIdleTimeout from "@/app/components/auth/SessionIdleTimeout";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <SessionIdleTimeout />
      <ThemeProvider>
        <AppBackground />
        {children}
      </ThemeProvider>
    </SessionProvider>
  );
}
