import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { LogOut, Search } from "lucide-react";
import { api, errMsg, fmtDate } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, StatCard, Loader, StatusBadge, EmptyState } from "@/components/sb/Kit";
import { ConfirmDialog } from "@/components/sb/ConfirmDialog";

export default function Admin() {
  const { signOut, user } = useAuth();
  const [stats, setStats] = useState(null);
  const [rows, setRows] = useState(null);
  const [logs, setLogs] = useState([]);
  const [q, setQ] = useState("");
  const [target, setTarget] = useState(null);
  const load = useCallback(() => {
    Promise.all([api.get("/admin/stats"), api.get("/admin/businesses"), api.get("/admin/audit")])
      .then(([s, b, a]) => { setStats(s.data); setRows(b.data); setLogs(a.data); })
      .catch((e) => toast.error(errMsg(e)));
  }, []);
  useEffect(() => { load(); }, [load]);
  const shown = (rows || []).filter((b) => !q || `${b.name} ${b.owner_name} ${b.owner_phone} ${b.location}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="min-h-screen bg-[#F7F5F0]" data-testid="admin-page">
      <header className="flex h-14 items-center justify-between bg-[#171717] px-4 text-[#F7F5F0] sm:px-8">
        <div className="flex items-center gap-2"><div className="flex h-8 w-8 items-center justify-center rounded-md bg-[#8B1E2D] font-display font-bold">S</div><span className="font-display font-bold">StaffBook</span><span className="rounded bg-[#C6A15B] px-2 py-0.5 text-[10px] font-bold uppercase text-[#171717]">Super Admin</span></div>
        <button className="btn-ghost btn-sm !text-stone-300" onClick={signOut} data-testid="admin-logout-btn"><LogOut className="h-4 w-4" /> {user?.name}</button>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6 sm:px-8">
        <PageHeader title="Platform overview" subtitle="All registered businesses on StaffBook." />
        {!stats ? <Loader /> : (
          <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
            <StatCard tone="dark" label="Registered businesses" value={stats.total_businesses} testid="admin-stat-total" />
            <StatCard label="Active" value={stats.active_businesses} testid="admin-stat-active" />
            <StatCard label="Inactive" value={stats.inactive_businesses} testid="admin-stat-inactive" />
            <StatCard label="Active staff (all)" value={stats.total_staff} hint={`${stats.total_staff_all} incl. former`} testid="admin-stat-staff" />
          </div>
        )}
        <div className="relative mb-3"><Search className="absolute left-3 top-3 h-4 w-4 text-stone-400" /><input className="inp pl-9" placeholder="Search businesses" value={q} onChange={(e) => setQ(e.target.value)} data-testid="admin-search-input" /></div>
        {!rows ? <Loader /> : shown.length === 0 ? <EmptyState title="No businesses yet" /> : (
          <div className="card overflow-x-auto">
            <table className="tbl" data-testid="admin-business-table">
              <thead><tr><th>Business</th><th>Owner</th><th>Registered</th><th>Active staff</th><th>Status</th><th></th></tr></thead>
              <tbody>{shown.map((b) => (
                <tr key={b.id} data-testid="admin-business-row">
                  <td><div className="font-semibold">{b.name}</div><div className="text-xs text-stone-500">{b.type || "—"} · {b.location || "—"}</div></td>
                  <td>{b.owner_name}<div className="font-num text-xs text-stone-500">{b.owner_phone}</div></td>
                  <td>{fmtDate(b.created_at)}</td>
                  <td className="font-num">{b.active_staff}</td>
                  <td><StatusBadge status={b.status} /></td>
                  <td className="text-right">
                    <button className={b.status === "active" ? "btn-outline btn-sm" : "btn-gold btn-sm"} onClick={() => setTarget(b)} data-testid={`admin-toggle-${b.id}`}>{b.status === "active" ? "Deactivate" : "Activate"}</button>
                  </td>
                </tr>))}</tbody>
            </table>
          </div>
        )}
        <section className="card mt-6 p-5">
          <h3 className="font-semibold">Admin audit log</h3>
          <div className="mt-3 max-h-72 overflow-y-auto text-xs" data-testid="admin-audit-log">
            {logs.length === 0 && <div className="text-stone-500">No administrative actions yet.</div>}
            {logs.map((l) => <div key={l.id} className="border-b border-stone-100 py-2"><span className="font-semibold">{l.action}</span> · {rows?.find((b) => b.id === l.entity_id)?.name || l.entity_id} · {new Date(l.created_at).toLocaleString("en-IN")} {l.details?.reason && `· ${l.details.reason}`}</div>)}
          </div>
        </section>
      </main>
      <ConfirmDialog open={!!target} onOpenChange={(o) => !o && setTarget(null)} danger={target?.status === "active"} requireReason
        title={target?.status === "active" ? `Deactivate ${target?.name}?` : `Activate ${target?.name}?`}
        description={target?.status === "active" ? "The owner and staff will be blocked from logging in to this business. No data is deleted." : "The business will regain full access."}
        confirmLabel={target?.status === "active" ? "Deactivate" : "Activate"}
        onConfirm={async (reason) => {
          try { await api.post(`/admin/businesses/${target.id}/status`, { active: target.status !== "active", reason }); toast.success("Business updated"); load(); } catch (e) { toast.error(errMsg(e)); }
        }} />
    </div>
  );
}
