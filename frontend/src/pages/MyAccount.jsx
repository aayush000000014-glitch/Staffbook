import { useEffect, useState } from "react";
import { LogOut } from "lucide-react";
import { api, errMsg, inr, fmtDate, LABELS } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { StatCard, Loader, StatusBadge, ErrorBox, EmptyState } from "@/components/sb/Kit";
import { Breakdown } from "@/components/sb/ObligationDialog";

export default function MyAccount() {
  const { signOut } = useAuth();
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState(null);
  useEffect(() => { api.get("/me/staff").then((r) => setD(r.data)).catch((e) => setErr(errMsg(e))); }, []);
  return (
    <div className="min-h-screen bg-[#F7F5F0]" data-testid="my-account-page">
      <header className="flex h-14 items-center justify-between bg-[#171717] px-4 text-[#F7F5F0]">
        <div><span className="font-display font-bold">StaffBook</span> <span className="text-xs text-[#C6A15B]">{d?.business.name}</span></div>
        <button className="btn-ghost btn-sm !text-stone-300" onClick={signOut} data-testid="staff-logout-btn"><LogOut className="h-4 w-4" /> Log out</button>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-6">
        <ErrorBox error={err} />
        {!d ? !err && <Loader /> : (
          <>
            <h1 className="text-2xl font-bold">{d.staff.name}</h1>
            <p className="mb-5 text-sm text-stone-600">{d.staff.designation} · Joined {fmtDate(d.staff.joining_date)}</p>
            <div className="mb-6 grid grid-cols-2 gap-3">
              <StatCard tone="dark" label="Earned this month" value={d.this_month.earned} money testid="me-earned" />
              <StatCard label="Advance balance" value={d.advances.outstanding} money testid="me-advance" />
              <StatCard label="Paid leave left" value={`${d.leave.remaining} / ${d.leave.quota}`} hint={LABELS[d.leave.period]} testid="me-leave" />
              <StatCard label="Outstanding salary" value={d.obligations.filter((v) => !v.accruing).reduce((a, v) => a + v.balance, 0)} money hint="Completed salary periods" testid="me-outstanding" />
            </div>
            <h3 className="mb-2 font-semibold">Salary periods</h3>
            {d.obligations.length === 0 ? <EmptyState title="No salary periods yet" /> : (
              <div className="grid gap-2" data-testid="me-obligations">
                {d.obligations.map((v) => (
                  <div key={v.id} className="card p-4">
                    <button className="flex w-full items-center justify-between text-left" onClick={() => setOpen(open === v.id ? null : v.id)}>
                      <div><div className="font-medium">{fmtDate(v.period_start)} – {fmtDate(v.period_end)}</div><div className="text-xs text-stone-500">Due {fmtDate(v.due_date)} · Paid {inr(v.paid)}</div></div>
                      <div className="flex items-center gap-2"><span className="font-num text-sm">{inr(v.net_payable)}</span><StatusBadge status={v.status} /></div>
                    </button>
                    {open === v.id && <div className="mt-3"><Breakdown v={v} /></div>}
                  </div>
                ))}
              </div>
            )}
            <h3 className="mb-2 mt-6 font-semibold">Attendance exceptions</h3>
            {d.attendance.length === 0 ? <EmptyState title="No exceptions — always present" /> : (
              <div className="card divide-y divide-stone-100">
                {d.attendance.map((a) => <div key={a.date} className="flex justify-between p-3 text-sm"><span>{fmtDate(a.date)}</span><StatusBadge status={a.status} /></div>)}
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}
