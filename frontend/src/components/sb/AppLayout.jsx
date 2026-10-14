import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { LayoutDashboard, Users, CalendarCheck, Wallet, FileBarChart, Settings, LogOut, Bell, Menu } from "lucide-react";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useAuth } from "@/context/AuthContext";
import { api, fmtDate } from "@/lib/api";

const NAV = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/staff", label: "Staff", icon: Users },
  { to: "/attendance", label: "Attendance", icon: CalendarCheck },
  { to: "/payments", label: "Payments", icon: Wallet },
  { to: "/reports", label: "Reports", icon: FileBarChart },
  { to: "/settings", label: "Settings", icon: Settings },
];

const Brand = ({ business }) => (
  <div className="flex items-center gap-3">
    {business?.logo ? (
      <img src={business.logo} alt="" className="h-9 w-9 rounded-lg object-cover" />
    ) : (
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#8B1E2D] font-display text-lg font-bold text-white">S</div>
    )}
    <div className="min-w-0">
      <div className="font-display text-base font-bold leading-tight">StaffBook</div>
      <div className="truncate text-xs text-[#C6A15B]" data-testid="nav-business-name">{business?.name}</div>
    </div>
  </div>
);

function NotificationsSheet({ open, onOpenChange }) {
  const [items, setItems] = useState(null);
  const nav = useNavigate();
  useEffect(() => {
    if (open) {
      api.get("/notifications").then((r) => setItems(r.data)).catch(() => setItems([]));
    }
  }, [open]);
  const readAll = async () => {
    await api.post("/notifications/read-all");
    setItems((x) => x.map((n) => ({ ...n, read: true })));
  };
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="w-full overflow-y-auto sm:max-w-md" data-testid="notifications-panel">
        <SheetHeader><SheetTitle>Notifications</SheetTitle></SheetHeader>
        <button className="btn-outline btn-sm mt-3" onClick={readAll} data-testid="notifications-read-all">Mark all as read</button>
        <div className="mt-4 space-y-2">
          {items === null && <div className="text-sm text-stone-500">Loading…</div>}
          {items?.length === 0 && <div className="text-sm text-stone-500">No notifications yet.</div>}
          {items?.map((n) => (
            <button key={n.id} onClick={() => { onOpenChange(false); nav(`/payments?open=${n.obligation_id}`); }}
              className={`w-full rounded-lg border p-3 text-left text-sm ${n.read ? "border-stone-200 bg-white" : "border-[#C6A15B] bg-[#C6A15B]/10"}`} data-testid="notification-item">
              <div>{n.message}</div>
              <div className="mt-1 text-xs text-stone-500">{fmtDate(n.created_at)}</div>
            </button>
          ))}
        </div>
      </SheetContent>
    </Sheet>
  );
}

export default function AppLayout() {
  const { business, user, signOut } = useAuth();
  const [notif, setNotif] = useState(false);
  const [more, setMore] = useState(false);
  const nav = useNavigate();
  const logout = async () => { await signOut(); nav("/login"); };
  const link = ({ isActive }) =>
    `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors ${isActive ? "bg-[#8B1E2D] text-white" : "text-stone-300 hover:bg-white/5 hover:text-white"}`;
  return (
    <div className="min-h-screen bg-[#F7F5F0]">
      <aside className="no-print fixed bottom-0 left-0 top-0 z-40 hidden w-64 flex-col border-r border-[#27272A] bg-[#171717] p-4 text-[#F7F5F0] md:flex">
        <Brand business={business} />
        <nav className="mt-8 flex flex-1 flex-col gap-1">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} className={link} data-testid={`sidebar-${n.label.toLowerCase()}`}>
              <n.icon className="h-4 w-4" /> {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-white/10 pt-4">
          <div className="mb-2 truncate px-3 text-xs text-stone-400">{user?.name} · {user?.phone}</div>
          <button onClick={logout} className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-stone-300 hover:bg-white/5" data-testid="logout-btn">
            <LogOut className="h-4 w-4" /> Log out
          </button>
        </div>
      </aside>

      <header className="no-print sticky top-0 z-30 flex h-14 items-center justify-between border-b border-stone-200 bg-[#F7F5F0]/90 px-4 backdrop-blur md:ml-64 md:px-8">
        <div className="md:hidden text-[#171717]"><span className="font-display font-bold">StaffBook</span><span className="ml-2 text-xs text-stone-500">{business?.name}</span></div>
        <div className="hidden text-sm text-stone-500 md:block">{fmtDate(new Date().toISOString())}</div>
        <button className="btn-ghost btn-sm" onClick={() => setNotif(true)} data-testid="notifications-btn"><Bell className="h-4 w-4" /> <span className="hidden sm:inline">Alerts</span></button>
      </header>

      <main className="print-area px-4 pb-24 pt-5 sm:px-6 md:ml-64 md:px-8 md:pb-10">
        <Outlet />
      </main>

      <nav className="no-print fixed bottom-0 left-0 right-0 z-40 flex h-16 items-center justify-around border-t border-[#27272A] bg-[#171717] text-[#F7F5F0] md:hidden">
        {NAV.slice(0, 4).map((n) => (
          <NavLink key={n.to} to={n.to} data-testid={`bottomnav-${n.label.toLowerCase()}`}
            className={({ isActive }) => `flex flex-col items-center gap-0.5 px-2 text-[10px] ${isActive ? "text-[#C6A15B]" : "text-stone-400"}`}>
            <n.icon className="h-5 w-5" /> {n.label}
          </NavLink>
        ))}
        <button onClick={() => setMore(true)} className="flex flex-col items-center gap-0.5 px-2 text-[10px] text-stone-400" data-testid="bottomnav-more">
          <Menu className="h-5 w-5" /> More
        </button>
      </nav>

      <Sheet open={more} onOpenChange={setMore}>
        <SheetContent side="bottom" className="bg-[#171717] text-[#F7F5F0]" data-testid="more-sheet">
          <div className="grid gap-1 pt-4">
            {NAV.slice(4).map((n) => (
              <NavLink key={n.to} to={n.to} className={link} onClick={() => setMore(false)} data-testid={`more-${n.label.toLowerCase()}`}>
                <n.icon className="h-4 w-4" /> {n.label}
              </NavLink>
            ))}
            <button onClick={logout} className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-stone-300" data-testid="mobile-logout-btn"><LogOut className="h-4 w-4" /> Log out</button>
          </div>
        </SheetContent>
      </Sheet>
      <NotificationsSheet open={notif} onOpenChange={setNotif} />
    </div>
  );
}
