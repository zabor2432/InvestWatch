import { Eye, EyeOff, Moon, RefreshCw, ShieldCheck, Sun, Wifi, WifiOff } from "lucide-react";
import type { ReactNode } from "react";
import type { ConnectionState } from "../api";
import type { Theme } from "../hooks/useTheme";
import { cn } from "./ui/cn";

export type View = "overview" | "results" | "report" | "calibration";

interface Props {
  view: View;
  threshold: number;
  connection: ConnectionState;
  theme: Theme;
  blind: boolean;
  refreshing: boolean;
  onRefresh: () => void;
  onToggleBlind: () => void;
  onView: (v: View) => void;
  onToggleTheme: () => void;
  notifications: ReactNode;
}

const CONN: Record<ConnectionState, string> = { open: "Na żywo", connecting: "Łączenie…", closed: "Rozłączono" };

export function Header({ view, threshold, connection, theme, blind, refreshing, onRefresh, onToggleBlind, onView, onToggleTheme, notifications }: Props) {
  const tab = (v: View, label: string) => (
    <button type="button" onClick={() => onView(v)} aria-current={view === v ? "page" : undefined} className={cn("h-full border-b-2 px-3 text-sm font-medium", view === v ? "border-accent text-fg" : "border-transparent text-muted hover:text-fg")}>
      {label}
    </button>
  );
  return (
    <header className="flex h-12 shrink-0 items-center gap-4 border-b border-line bg-surface px-4">
      <div className="flex items-center gap-2 font-semibold"><ShieldCheck className="h-5 w-5 text-accent" aria-hidden /> InvestAlert</div>
      <nav className="flex h-full" aria-label="Główna nawigacja">{tab("overview", "Przegląd")}{tab("results", "Wyniki")}{tab("report", "Raport")}{tab("calibration", "Kalibracja")}</nav>
      <div className="ml-auto flex items-center gap-3">
        <button type="button" onClick={onRefresh} disabled={refreshing} aria-busy={refreshing} className="inline-flex h-8 items-center gap-1.5 rounded border border-line px-2 text-xs hover:bg-raised disabled:opacity-60" title="Przetwarza nowe materiały w Dagsterze i odświeża listę">
          <RefreshCw className={cn("h-3.5 w-3.5", refreshing && "animate-spin")} aria-hidden /> {refreshing ? "Przetwarzanie…" : "Odśwież dane"}
        </button>
        <button type="button" onClick={onToggleBlind} aria-pressed={blind} className={cn("inline-flex h-8 items-center gap-1.5 rounded border px-2 text-xs", blind ? "border-accent text-accent" : "border-line text-muted hover:bg-raised")} title="Tryb ślepy ukrywa odpowiedzi modelu do czasu zatwierdzenia własnej oceny">
          {blind ? <EyeOff className="h-3.5 w-3.5" aria-hidden /> : <Eye className="h-3.5 w-3.5" aria-hidden />} Tryb ślepy {blind ? "wł." : "wył."}
        </button>
        <button type="button" onClick={() => onView("calibration")} className="rounded border border-line px-2 py-1 text-xs text-muted hover:bg-raised" title="Przejdź do kalibracji progu">
          Próg <b className="font-mono text-fg">{threshold.toFixed(2)}</b>
        </button>
        <span className={cn("flex items-center gap-1 text-xs", connection === "open" ? "text-risk-low" : "text-risk-mid")} role="status">
          {connection === "open" ? <Wifi className="h-3.5 w-3.5" aria-hidden /> : <WifiOff className="h-3.5 w-3.5" aria-hidden />}
          {CONN[connection]}
        </span>
        {notifications}
        <button type="button" onClick={onToggleTheme} className="inline-flex h-8 w-8 items-center justify-center rounded border border-line bg-surface hover:bg-raised" aria-label={theme === "dark" ? "Przełącz na jasny motyw" : "Przełącz na ciemny motyw"}>
          {theme === "dark" ? <Sun className="h-4 w-4" aria-hidden /> : <Moon className="h-4 w-4" aria-hidden />}
        </button>
      </div>
    </header>
  );
}
