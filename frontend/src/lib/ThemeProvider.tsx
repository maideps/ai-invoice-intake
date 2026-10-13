import { useCallback, useEffect, useState, type ReactNode } from "react";

import { writeSetting } from "./storage";
import { applyTheme, savedTheme, ThemeContext, THEME_KEY, THEMES, type ThemeChoice } from "./theme";

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<ThemeChoice>(savedTheme);

  useEffect(() => {
    applyTheme(theme);
    if (theme !== "system" || typeof window.matchMedia !== "function") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => applyTheme("system");
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, [theme]);

  const setTheme = useCallback((choice: ThemeChoice) => {
    writeSetting(THEME_KEY, choice);
    setThemeState(choice);
  }, []);

  const cycleTheme = useCallback(() => {
    setTheme(THEMES[(THEMES.indexOf(theme) + 1) % THEMES.length]!);
  }, [setTheme, theme]);

  return <ThemeContext.Provider value={{ theme, setTheme, cycleTheme }}>{children}</ThemeContext.Provider>;
}
