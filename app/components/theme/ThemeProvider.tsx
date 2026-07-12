"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { themeTokens, type ThemeColors, type ThemeMode } from "@/lib/theme/tokens";

type ThemeContextValue = {
  mode: ThemeMode;
  colors: ThemeColors;
  toggleTheme: () => void;
  setMode: (mode: ThemeMode) => void;
};

const ThemeContext = createContext<ThemeContextValue | null>(null);

function getInitialMode(): ThemeMode {
  if (typeof window === "undefined") return "dark";
  const stored = window.localStorage.getItem("gpt-theme") as ThemeMode | null;
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [mode, setModeState] = useState<ThemeMode>("dark");
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setModeState(getInitialMode());
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;
    document.documentElement.dataset.theme = mode;
    window.localStorage.setItem("gpt-theme", mode);
  }, [mode, mounted]);

  const setMode = useCallback((next: ThemeMode) => setModeState(next), []);
  const toggleTheme = useCallback(
    () => setModeState((current) => (current === "dark" ? "light" : "dark")),
    [],
  );

  const value = useMemo(
    () => ({
      mode,
      colors: themeTokens[mode],
      toggleTheme,
      setMode,
    }),
    [mode, toggleTheme, setMode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error("useTheme debe usarse dentro de ThemeProvider");
  return context;
}
