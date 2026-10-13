import { FileCheck2 } from "lucide-react";
import { Link, NavLink, Outlet } from "react-router";

import { cn } from "@/lib/utils";

import { ActingAsPicker } from "./ActingAsPicker";
import { ThemeToggle } from "./ThemeToggle";

export function AppShell() {
  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md">
        <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4 sm:px-6">
          <Link to="/" className="flex items-center gap-2.5 font-semibold tracking-tight">
            <span className="flex size-7 items-center justify-center rounded-lg bg-accent text-accent-foreground">
              <FileCheck2 className="size-4" aria-hidden="true" />
            </span>
            Invoice intake
          </Link>
          <nav aria-label="Main" className="hidden text-sm sm:block">
            <NavLink
              to="/"
              end
              className={({ isActive }) =>
                cn(
                  "rounded-md px-2 py-1 transition-colors",
                  isActive ? "text-foreground" : "text-muted hover:text-foreground",
                )
              }
            >
              Review queue
            </NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-1">
            <ThemeToggle />
            <ActingAsPicker />
          </div>
        </div>
      </header>
      <main id="main" className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </div>
  );
}
