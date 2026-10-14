import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { UserPlus, CalendarX, HandCoins, Gavel, BadgeIndianRupee, CalendarDays, AlertTriangle } from "lucide-react";
import { api, errMsg, inr, fmtDate, LABELS } from "@/lib/api";
import { PageHeader, StatCard, Loader, StatusBadge, EmptyState, ErrorBox } from "@/components/sb/Kit";
import { StaffFormDialog } from "@/components/sb/StaffFormDialog";
import { AttendanceDialog, EntryDialog } from "@/components/sb/EntryDialogs";
import { ObligationDialog } from "@/components/sb/ObligationDialog";
import { useAuth } from "@/context/AuthContext";

const QUICK = [
  ["add-staff", "Add Staff", UserPlus], ["attendance", "Attendance Exception", CalendarX], ["advance", "Add Advance", HandCoins],
  ["fine", "Add Fine", Gavel], ["pay", "Mark Payment Given", BadgeIndianRupee], ["calendar", "Payment Calendar", CalendarDays],
];

const DueList = ({ items, onOpen, testid, empty }) =>
  items.length === 0 ? <div className="py-4 text-sm text-stone-500">{empty}</div> : (
    <div className="divide-y divide-stone-100" data-testid={testid}>
      {items.map((v) => (
        <button key={v.id} onClick={() => onOpen(v.id)} className="flex w-full items-center justify-between gap-3 py-3 text-left hover:bg-stone-50" data-testid={`${testid}-item`}>
          <div className="min-w-0">
            <div className="truncate font-medium">{v.staff_name}</div>
            <div className="text-xs text-stone-500">Due {fmtDate(v.due_date)} · {fmtDate(v.period_start)} – {fmtDate(v.period_end)}</div>
          </div>
          <div className="flex shrink-0 items-center gap-2"><span className="font-num text-sm font-semibold">{inr(v.balance)}</span><StatusBadge status={v.status} /></div>
        </button>
      ))}
    </div>
  );

export default function Dashboard() {
  const { business } = useAuth();
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [dlg, setDlg] = useState(null);
  const [oid, setOid] = useState(null);
  const nav = useNavigate();
  const load = useCallback(() => {
    api.get("/dashboard").then((r) => setD(r.data)).catch((e) => setErr(errMsg(e)));
  }, []);
  useEffect(() => { load(); }, [load]);
  const quick = (k) => {
    if (k === "pay") nav("/payments?status=open");
    else if (k === "calendar") nav("/payments?tab=calendar");
    else setDlg(k);
  };
  if (err) return <ErrorBox error={err} />;
  if (!d) return <Loader />;
  return (
    <div data-testid="dashboard-page">
      <PageHeader title={`Namaste, ${business?.name}`} subtitle={`Live figures as of ${fmtDate(d.today)}`} />
      {d.alerts.length > 0 && (
        <div className="mb-6 space-y-2" data-testid="dashboard-alerts">
          {d.alerts.slice(0, 4).map((a) => (
            <button key={a.id} onClick={() => a.obligation_id && setOid(a.obligation_id)} className={`flex w-full items-start gap-2 rounded-lg border px-3 py-2.5 text-left text-sm ${a.kind === "overdue" ? "border-red-200 bg-red-50 text-red-900" : "border-[#C6A15B]/50 bg-[#C6A15B]/10"}`} data-testid="dashboard-alert">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {a.message}
            </button>
          ))}
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard tone="dark" label="Active staff" value={d.active_staff} hint={`${d.capacity_remaining} of ${d.capacity} slots left`} testid="stat-active-staff" onClick={() => nav("/staff")} />
        <StatCard label="Present today" value={d.present_today} testid="stat-present-today" onClick={() => nav("/attendance")} />
        <StatCard label="Absent today" value={d.absent_today} hint="Absent + on leave" testid="stat-absent-today" onClick={() => nav("/attendance")} />
        <StatCard label="Earned till date" value={d.earned_till_date} money hint="This month, all active staff" testid="stat-earned" />
        <StatCard label="Payable this month" value={d.payable_this_month} money hint="Net of periods due this month" testid="stat-payable" />
        <StatCard label="Paid this month" value={d.paid_this_month} money testid="stat-paid" onClick={() => nav("/payments?tab=transactions")} />
        <StatCard label="Pending" value={d.pending.amount} money hint={`${d.pending.count} payment(s)`} testid="stat-pending" onClick={() => nav("/payments?status=pending")} />
        <StatCard tone={d.overdue.count ? "danger" : "default"} label="Overdue" value={d.overdue.amount} money hint={`${d.overdue.count} payment(s)`} testid="stat-overdue" onClick={() => nav("/payments?status=overdue")} />
      </div>

      <div className="mt-6 grid grid-cols-3 gap-2 sm:grid-cols-6" data-testid="quick-actions">
        {QUICK.map(([k, l, Icon]) => (
          <button key={k} onClick={() => quick(k)} className="card flex flex-col items-center gap-2 p-3 text-center text-xs font-semibold hover:border-[#8B1E2D]" data-testid={`quick-${k}`}>
            <Icon className="h-5 w-5 text-[#8B1E2D]" /> {l}
          </button>
        ))}
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <div className="mb-1 flex items-center justify-between"><h3 className="font-semibold">Due in next 3 days</h3><span className="font-num text-sm">{inr(d.due_soon.amount)}</span></div>
          <DueList items={d.due_soon.items} onOpen={setOid} testid="due-soon-list" empty="No payments due in the next 3 days." />
        </div>
        <div className="card p-5">
          <div className="mb-1 flex items-center justify-between"><h3 className="font-semibold">Overdue</h3><span className="font-num text-sm text-[#8B1E2D]">{inr(d.overdue.amount)}</span></div>
          <DueList items={d.overdue.items} onOpen={setOid} testid="overdue-list" empty="Nothing overdue. Well done." />
        </div>
      </div>

      <div className="card mt-4 p-5">
        <h3 className="mb-2 font-semibold">Recent transactions</h3>
        {d.recent_transactions.length === 0 ? (
          <EmptyState title="No payments yet" hint="Record a salary payment from Payments to see it here." />
        ) : (
          <div className="divide-y divide-stone-100" data-testid="recent-transactions">
            {d.recent_transactions.map((t) => (
              <button key={t.id} onClick={() => setOid(t.obligation_id)} className="flex w-full items-center justify-between py-3 text-left text-sm hover:bg-stone-50">
                <div><div className="font-medium">{t.staff_name}</div><div className="text-xs text-stone-500">{fmtDate(t.date)} · {LABELS[t.method]}</div></div>
                <span className="font-num font-semibold">{inr(t.amount)}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <StaffFormDialog open={dlg === "add-staff"} onOpenChange={(o) => !o && setDlg(null)} onSaved={load} />
      <AttendanceDialog open={dlg === "attendance"} onOpenChange={(o) => !o && setDlg(null)} onSaved={load} />
      <EntryDialog kind="advance" open={dlg === "advance"} onOpenChange={(o) => !o && setDlg(null)} onSaved={load} />
      <EntryDialog kind="fine" open={dlg === "fine"} onOpenChange={(o) => !o && setDlg(null)} onSaved={load} />
      <ObligationDialog oid={oid} onOpenChange={(o) => !o && setOid(null)} onChanged={load} />
    </div>
  );
}
