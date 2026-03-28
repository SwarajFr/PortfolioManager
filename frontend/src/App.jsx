import { useEffect, useState } from "react";
import api from "./api/client";
import Login from "./pages/Login";
import Overview from "./pages/Overview";
import ExitSignals from "./pages/ExitSignals";
import Header from "./components/layout/Header";

const TABS = [
  { id: "overview", label: "Portfolio Overview" },
  { id: "exit",     label: "Exit Signals" },
];

export default function App() {
  const [auth, setAuth] = useState(null);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    api.get("/auth/status")
      .then(res => setAuth(res.data.authenticated))
      .catch(() => setAuth(false));
  }, []);

  if (auth === null) return <div className="p-6">Loading...</div>;

  if (!auth) return <Login />;

  return (
    <div>
      <Header />

      {/* Tab bar */}
      <div className="border-b border-neutral-800 px-6">
        <nav className="flex gap-1 max-w-7xl mx-auto">
          {TABS.map(tab => (
            <button
              key={tab.id}
              id={`tab-${tab.id}`}
              onClick={() => setActiveTab(tab.id)}
              className={`
                px-4 py-2.5 text-sm font-medium transition-colors cursor-pointer
                ${activeTab === tab.id
                  ? "text-neutral-100 border-b-2 border-neutral-100"
                  : "text-neutral-500 hover:text-neutral-300 border-b-2 border-transparent"
                }
              `}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Page content */}
      {activeTab === "overview" && <Overview />}
      {activeTab === "exit" && <ExitSignals />}
    </div>
  );
}