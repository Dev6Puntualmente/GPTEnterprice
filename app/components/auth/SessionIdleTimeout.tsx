"use client";

import { useEffect, useRef, useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { isAgentBusy, subscribeAgentBusy } from "@/lib/agent-busy";

const IDLE_MS = Number(process.env.NEXT_PUBLIC_SESSION_IDLE_MS ?? 5 * 60 * 1000);

const ACTIVITY_EVENTS = ["mousedown", "keydown", "scroll", "touchstart", "click"] as const;

export default function SessionIdleTimeout() {
  const { status } = useSession();
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [agentBusy, setAgentBusy] = useState(false);

  useEffect(() => {
    setAgentBusy(isAgentBusy());
    return subscribeAgentBusy(() => setAgentBusy(isAgentBusy()));
  }, []);

  useEffect(() => {
    if (status !== "authenticated") {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
      return;
    }

    const logout = () => {
      void signOut({ callbackUrl: "/login" });
    };

    const clearTimer = () => {
      if (timerRef.current) {
        clearTimeout(timerRef.current);
        timerRef.current = null;
      }
    };

    const armTimer = () => {
      clearTimer();
      if (agentBusy || isAgentBusy()) {
        return;
      }
      timerRef.current = setTimeout(logout, IDLE_MS);
    };

    const resetTimer = () => {
      armTimer();
    };

    if (agentBusy) {
      clearTimer();
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, resetTimer);
      }
      return () => {
        clearTimer();
      };
    }

    for (const event of ACTIVITY_EVENTS) {
      window.addEventListener(event, resetTimer, { passive: true });
    }
    armTimer();

    return () => {
      clearTimer();
      for (const event of ACTIVITY_EVENTS) {
        window.removeEventListener(event, resetTimer);
      }
    };
  }, [status, agentBusy]);

  return null;
}
