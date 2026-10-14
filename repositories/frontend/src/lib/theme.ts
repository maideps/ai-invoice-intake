import { createContext, useContext } from "react";

import { readSetting } from "./storage";

export type ThemeChoice = "system" | "light" | "dark";

export const THEMES: ThemeChoice[] = ["system", "light", "dark"];
export const THEME_KEY = "theme";

export interface ThemeState {
  theme: ThemeChoice;
  setTheme: (choice: ThemeChoice) => void;
  /** system → light → dark → system */
  cycleTheme: () => void;
}

export const ThemeContext = createContext<ThemeState | null>(null);

export function useTheme(): ThemeState {
  const state = useContext(ThemeContext);
  if (!state) throw new Error("useTheme must be used inside ThemeProvider");
  return state;
}

export function systemPrefersDark(): boolean {
  return typeof window.matchMedia === "function"
    ? window.matchMedia("(prefers-color-scheme: dark)").matches
    : false;
}

export function applyTheme(choice: ThemeChoice): void {
  const dark = choice === "dark" || (choice === "system" && systemPrefersDark());
  document.documentElement.classList.toggle("dark", dark);
}

export function savedTheme(): ThemeChoice {
  const saved = readSetting(THEME_KEY);
  return THEMES.includes(saved as ThemeChoice) ? (saved as ThemeChoice) : "system";
}
