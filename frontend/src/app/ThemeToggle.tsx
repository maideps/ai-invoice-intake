import { Monitor, Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useTheme, type ThemeChoice } from "@/lib/theme";

const LABELS: Record<ThemeChoice, string> = {
  system: "Theme: follows your system",
  light: "Theme: light",
  dark: "Theme: dark",
};

export function ThemeToggle() {
  const { theme, cycleTheme } = useTheme();
  const Icon = theme === "light" ? Sun : theme === "dark" ? Moon : Monitor;
  return (
    <Button variant="ghost" size="icon" onClick={cycleTheme} aria-label={LABELS[theme]} title={LABELS[theme]}>
      <Icon />
    </Button>
  );
}
