/**
 * Root: decides login vs. shell, and which feature page is mounted.
 *
 * Navigation is a string in state against a `PAGES` lookup rather than a
 * router. There are four destinations, no URLs worth deep-linking, and nothing
 * nested — a router would add a dependency and a build step to solve a problem
 * this app does not have. The cost is real though: **switching views unmounts
 * the previous page**, so any page-local `useState` is discarded. State that
 * must outlive a view switch belongs in a module-level store read through
 * `useSyncExternalStore`, not in the page.
 *
 * Pages are `lazy` so a cold load ships only the shell and the overview; the
 * heavier fragility and screener bundles arrive when first opened.
 *
 * `auth === null` is the third state, distinct from logged-out: it means the
 * status call has not resolved. Without it the login page would flash on every
 * refresh before the session check came back.
 */
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

const PAGES = {
  overview: PortfolioOverviewPage,
  exit: ExitSignalsPage,
  fragility: FragilityPage,
  screener: ScreenerPage,
};

export default function App() {
  const [auth, setAuth] = useState(null);
  const [activeView, setActiveView] = useState("overview");

  useEffect(() => {
    let cancelled = false;

    getAuthStatus()
      .then((status) => {
        if (!cancelled) setAuth(status);
      })
      .catch(() => {
        if (!cancelled) setAuth({ authenticated: false, userId: null });
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const ActivePage = PAGES[activeView] || PortfolioOverviewPage;

  if (auth === null) {
    return (
      <>
        <LoadingState title="Connecting" />
        <Toaster position="top-right" toastOptions={{ className: "terminal-toast" }} />
      </>
    );
  }

  if (!auth.authenticated) {
    return (
      <>
        <LoginPage />
        <Toaster position="top-right" toastOptions={{ className: "terminal-toast" }} />
      </>
    );
  }

  return (
    <>
      <AppShell activeView={activeView} onViewChange={setActiveView} userId={auth.userId}>
        <Suspense fallback={<LoadingState title="Loading module" />}>
          <ActivePage />
        </Suspense>
      </AppShell>
      <Toaster position="top-right" toastOptions={{ className: "terminal-toast" }} />
    </>
  );
}
