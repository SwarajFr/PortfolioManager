import { NAV_ITEMS } from "../../constants/navigation";
import TopBar from "./TopBar";

export default function AppShell({ activeView, children, onViewChange, userId }) {
  const activeItem = NAV_ITEMS.find((item) => item.id === activeView) || NAV_ITEMS[0];

  return (
    <div className="flex min-h-screen bg-dashboard text-[var(--color-text)]">
      <div className="flex min-h-screen w-full flex-col lg:flex-row">
        <TopBar activeItem={activeItem} onViewChange={onViewChange} userId={userId} />
        <main className="min-h-0 w-full flex-1 overflow-x-hidden overflow-y-auto px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
