import { lazy, Suspense, useEffect, useState } from "react";
import { Toaster } from "react-hot-toast";
import AppShell from "../components/layout/AppShell";
import LoadingState from "../components/ui/LoadingState";
import { getAuthStatus } from "../services/authService";
import LoginPage from "../features/auth/LoginPage";

const PortfolioOverviewPage = lazy(() => import("../features/portfolio/PortfolioOverviewPage"));
const ExitSignalsPage = lazy(() => import("../features/exit-signals/ExitSignalsPage"));
const FragilityPage = lazy(() => import("../features/fragility/FragilityPage"));
const ScreenerPage = lazy(() => import("../features/screener/ScreenerPage"));
const AgentPage = lazy(() => import("../features/agent/AgentPage"));

const PAGES = {
  overview: PortfolioOverviewPage,
  exit: ExitSignalsPage,
  fragility: FragilityPage,
  screener: ScreenerPage,
  agent: AgentPage,
};

export default function App() {
  const [authenticated, setAuthenticated] = useState(null);
  const [activeView, setActiveView] = useState("overview");

  useEffect(() => {
    let cancelled = false;

    getAuthStatus()
      .then((status) => {
        if (!cancelled) setAuthenticated(status);
      })
      .catch(() => {
        if (!cancelled) setAuthenticated(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const ActivePage = PAGES[activeView] || PortfolioOverviewPage;

  if (authenticated === null) {
    return (
      <>
        <LoadingState title="Connecting" />
        <Toaster position="top-right" toastOptions={{ className: "terminal-toast" }} />
      </>
    );
  }

  if (!authenticated) {
    return (
      <>
        <LoginPage />
        <Toaster position="top-right" toastOptions={{ className: "terminal-toast" }} />
      </>
    );
  }

  return (
    <>
      <AppShell activeView={activeView} onViewChange={setActiveView}>
        <Suspense fallback={<LoadingState title="Loading module" />}>
          <ActivePage />
        </Suspense>
      </AppShell>
      <Toaster position="top-right" toastOptions={{ className: "terminal-toast" }} />
    </>
  );
}
