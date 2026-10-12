import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";

export function Logo() {
  return (
    <span className="flex items-center gap-2">
      <span className="relative inline-flex h-5 w-5 items-center justify-center rounded-full bg-pin-fix">
        <span className="h-1.5 w-1.5 rounded-full bg-pin-foreground" />
      </span>
      <span className="font-display text-xl tracking-tight">Pinpoint</span>
    </span>
  );
}

export function AppHeader({ children, linkHome = true }: { children?: ReactNode; linkHome?: boolean }) {
  return (
    <header className="flex h-14 shrink-0 items-center gap-4 border-b border-border bg-background px-5">
      {linkHome ? (
        <Link to="/" aria-label="Pinpoint home">
          <Logo />
        </Link>
      ) : (
        <Logo />
      )}
      {children}
    </header>
  );
}

export function StatusBadge({ status }: { status: "open" | "approved" | "closed" }) {
  const cls =
    status === "open"
      ? "bg-pin-question/20 text-foreground"
      : status === "approved"
        ? "bg-pin-like/20 text-foreground"
        : "bg-muted text-muted-foreground";
  return <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${cls}`}>{status}</span>;
}
