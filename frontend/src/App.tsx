import { lazy, Suspense, useCallback, useMemo, useRef, useState } from "react";
import { CalibrationPanel } from "./components/CalibrationPanel";
import { Header, type View } from "./components/Header";
import { NotificationCenter } from "./components/NotificationCenter";
import { Toaster } from "./components/Toaster";
import { activeFilterCount, applyFilters } from "./domain/filters";
import { STATUS_LABEL, STATUSES } from "./domain/labels";
import type { AlertEvent } from "./domain/types";
import { useAlerts } from "./hooks/useAlerts";
import { useFilters } from "./hooks/useFilters";
import { useHotkeys } from "./hooks/useHotkeys";
import { usePersistedState } from "./hooks/usePersistedState";
import { useRecords } from "./hooks/useRecords";
import { useRefresh, type RefreshResult } from "./hooks/useRefresh";
import { useTheme } from "./hooks/useTheme";
import { useThreshold } from "./hooks/useThreshold";
import { useToasts } from "./hooks/useToasts";
import { ReportPage } from "./pages/ReportPage";
import { ResultsPage } from "./pages/ResultsPage";

const OverviewPage = lazy(() => import("./pages/OverviewPage").then((m) => ({ default: m.OverviewPage })));

export default function App() {
  const [view, setView] = useState<View>(() => (location.hash === "#kalibracja" ? "calibration" : location.hash === "#przeglad" ? "overview" : location.hash === "#raport" ? "report" : "results"));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [notifOpen, setNotifOpen] = useState(false);
  const searchRef = useRef<HTMLInputElement>(null);

  const { theme, toggle } = useTheme();
  const [blind, setBlind] = usePersistedState("iw.blind", true); // tryb ślepy domyślnie włączony
  const { thresholds, setGlobal, setRule, setRules, resetRules, reset } = useThreshold();
  const { filters, patch, reset: resetFilters } = useFilters();
  const { records, loading, error, reload, updateStatus, prepend } = useRecords();
  const { toasts, push, dismiss } = useToasts();

  const onRefreshDone = useCallback((result: RefreshResult) => {
    if (result === "success") reload();
    push(result === "success" ? { tone: "success", title: "Dane odświeżone", description: "Przetwarzanie w Dagsterze zakończone." }
      : { tone: "danger", title: result === "failure" ? "Przetwarzanie zakończyło się błędem" : "Nie udało się uruchomić przetwarzania", description: result === "failure" ? "Szczegóły w Dagsterze (:3001)." : "Sprawdź, czy Dagster działa." });
  }, [reload, push]);
  const { refreshing, refresh } = useRefresh(onRefreshDone);

  const onAlert = useCallback((e: AlertEvent) => {
    prepend(e.record);
    push({ tone: "danger", title: "Wykryto wysokie ryzyko", description: `${e.record.entity.name}: ${e.record.title}`, recordId: e.record.id });
  }, [prepend, push]);
  const { connection, notifications, unread, markAllRead } = useAlerts(onAlert);

  const visible = useMemo(() => applyFilters(records, filters, thresholds), [records, filters, thresholds]);
  const selected = useMemo(() => records.find((r) => r.id === selectedId) ?? null, [records, selectedId]);

  const changeView = (v: View) => { setView(v); history.replaceState(null, "", v === "calibration" ? "#kalibracja" : v === "overview" ? "#przeglad" : v === "report" ? "#raport" : location.pathname + location.search); };
  const openRecord = useCallback((id: string | null) => { setSelectedId(id); if (id) setView("results"); }, []);

  const setStatus = useCallback(async (id: string, status: Parameters<typeof updateStatus>[1]) => {
    const ok = await updateStatus(id, status);
    push(ok ? { tone: "success", title: `Status: ${STATUS_LABEL[status]}`, description: id } : { tone: "danger", title: "Nie udało się zmienić statusu", description: "Zmiana została cofnięta." });
  }, [updateStatus, push]);

  const move = (delta: number) => {
    if (view !== "results" || visible.length === 0) return;
    const i = visible.findIndex((r) => r.id === selectedId);
    const next = visible[Math.min(visible.length - 1, Math.max(0, i === -1 ? (delta > 0 ? 0 : visible.length - 1) : i + delta))];
    setSelectedId(next.id);
  };

  useHotkeys({
    j: () => move(1),
    k: () => move(-1),
    "/": (e) => { if (view === "results") { e.preventDefault(); searchRef.current?.focus(); } },
    Escape: () => { if (notifOpen) setNotifOpen(false); else setSelectedId(null); },
    n: () => setNotifOpen((o) => !o),
    t: toggle,
    ...Object.fromEntries(STATUSES.map((s, i) => [String(i + 1), () => { if (view === "results" && selectedId) void setStatus(selectedId, s); }])),
  });

  return (
    <div className="flex h-full flex-col">
      <Header
        view={view}
        threshold={thresholds.global}
        connection={connection}
        theme={theme}
        blind={blind}
        refreshing={refreshing}
        onRefresh={() => void refresh()}
        onToggleBlind={() => setBlind(!blind)}
        onView={changeView}
        onToggleTheme={toggle}
        notifications={<NotificationCenter items={notifications} unread={unread} open={notifOpen} onOpenChange={(o) => { setNotifOpen(o); if (!o) markAllRead(); }} onOpenRecord={openRecord} />}
      />
      <main className="min-h-0 flex-1 overflow-auto">
        {view === "overview" ? (
          <Suspense fallback={<p className="p-8 text-center text-muted">Ładowanie…</p>}>
            <OverviewPage records={records} threshold={thresholds} />
          </Suspense>
        ) : view === "report" ? (
          <ReportPage records={records} threshold={thresholds} onOpenRecord={openRecord} />
        ) : view === "results" ? (
          <ResultsPage
            records={visible}
            total={records.length}
            filters={filters}
            activeFilters={activeFilterCount(filters)}
            loading={loading}
            error={error}
            selected={selected}
            history={selected ? records.filter((r) => r.observationId && r.observationId === selected.observationId && r.id !== selected.id) : []}
            blind={blind}
            threshold={thresholds}
            searchRef={searchRef}
            onFilters={patch}
            onResetFilters={resetFilters}
            onSelect={openRecord}
            onStatus={(id, s) => void setStatus(id, s)}
            onRetry={reload}
          />
        ) : (
          <CalibrationPanel records={records} thresholds={thresholds} onGlobal={setGlobal} onRule={setRule} onRules={setRules} onResetRules={resetRules} onReset={reset} />
        )}
      </main>
      <Toaster toasts={toasts} onDismiss={dismiss} onOpenRecord={openRecord} />
    </div>
  );
}
