import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Pencil, CalendarX, HandCoins, Gavel, LogOut, KeyRound, Play } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, errMsg, inr, fmtDate, todayISO, LABELS } from "@/lib/api";
import { Loader, StatCard, StatusBadge, Avatar, ErrorBox, EmptyState, Field } from "@/components/sb/Kit";
import { StaffFormDialog } from "@/components/sb/StaffFormDialog";
import { AttendanceDialog, EntryDialog } from "@/components/sb/EntryDialogs";
import { ObligationDialog } from "@/components/sb/ObligationDialog";
import { ConfirmDialog } from "@/components/sb/ConfirmDialog";
import { PhoneInput } from "@/components/sb/AuthShell";

const List = ({ items, empty, render, testid }) =>
  items.length === 0 ? <EmptyState title={empty} testid={`${testid}-empty`} /> : <div className="card divide-y divide-stone-100" data-testid={testid}>{items.map(render)}</div>;

function LeaveDialog({ open, onOpenChange, staff, onDone }) {
  const [date, setDate] = useState(todayISO());
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState(false);
  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-md" data-testid="leave-dialog">
          <DialogHeader><DialogTitle>Mark {staff.name} as left</DialogTitle></DialogHeader>
          <p className="text-sm text-stone-600">Salary stops accruing after the leaving date. All attendance, payments, advances and fines stay in history.</p>
          <Field label="Leaving date"><input type="date" className="inp" min={staff.joining_date} value={date} onChange={(e) => setDate(e.target.value)} data-testid="leave-date-input" /></Field>
          <Field label="Reason (optional)"><input className="inp" value={reason} onChange={(e) => setReason(e.target.value)} data-testid="leave-reason-input" /></Field>
          <div className="flex justify-end"><button className="btn-primary" onClick={() => setConfirm(true)} data-testid="leave-continue-btn">Continue</button></div>
        </DialogContent>
      </Dialog>
      <ConfirmDialog open={confirm} onOpenChange={setConfirm} danger title="Confirm leaving" confirmLabel="Mark as Left"
        description={`${staff.name} will move to Former Staff with leaving date ${fmtDate(date)}. This cannot be undone.`}
        onConfirm={async () => {
          try { await api.post(`/staff/${staff.id}/leave`, { leaving_date: date, reason }); toast.success("Marked as left"); onOpenChange(false); onDone(); } catch (e) { toast.error(errMsg(e)); }
        }} />
    </>
  );
}

function LoginDialog({ open, onOpenChange, staff, current, onDone }) {
  const [phone, setPhone] = useState("");
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const save = async (e) => {
    e.preventDefault();
    try { await api.post(`/staff/${staff.id}/login`, { phone, password: pw }); toast.success("Staff login saved"); onOpenChange(false); onDone(); } catch (ex) { setErr(errMsg(ex)); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="staff-login-dialog">
        <DialogHeader><DialogTitle>{current ? "Reset staff login" : "Give staff a login"}</DialogTitle></DialogHeader>
        <p className="text-sm text-stone-600">Staff can view only their own attendance, salary and payments. {current && `Current login: ${current}`}</p>
        <form onSubmit={save} className="grid gap-4">
          <Field label="Staff mobile"><PhoneInput value={phone} onChange={setPhone} testid="staff-login-phone-input" /></Field>
          <Field label="Password" hint="At least 8 characters. Share it with the staff member."><input type="text" className="inp" minLength={8} required value={pw} onChange={(e) => setPw(e.target.value)} data-testid="staff-login-password-input" /></Field>
          <ErrorBox error={err} />
          <div className="flex justify-end"><button className="btn-primary" data-testid="staff-login-submit">Save login</button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function StaffProfile() {
  const { id } = useParams();
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  const [dlg, setDlg] = useState(null);
  const [att, setAtt] = useState(null);
  const [oid, setOid] = useState(null);
  const [rev, setRev] = useState(null);
  const load = useCallback(() => {
    api.get(`/staff/${id}`).then((r) => setD(r.data)).catch((e) => setErr(errMsg(e)));
  }, [id]);
  useEffect(() => { load(); }, [load]);
  if (err) return <ErrorBox error={err} />;
  if (!d) return <Loader />;
  const s = d.staff;
  const active = s.status === "active";
  const close = (o) => !o && setDlg(null);
  return (
    <div data-testid="staff-profile-page">
      <Link to="/staff" className="mb-4 inline-flex items-center gap-1 text-sm text-stone-600 hover:text-[#8B1E2D]"><ArrowLeft className="h-4 w-4" /> Staff</Link>
      <div className="card mb-5 flex flex-col gap-4 p-5 sm:flex-row sm:items-center">
        <Avatar name={s.name} photo={s.photo} size={64} />
        <div className="flex-1">
          <div className="flex flex-wrap items-center gap-2"><h1 className="text-2xl font-bold" data-testid="profile-name">{s.name}</h1><StatusBadge status={s.status} testid="profile-status" />{s.cycle_paused && <StatusBadge status="pending" label="Cycle paused" />}</div>
          <div className="mt-1 text-sm text-stone-600">{s.designation || "—"} · {inr(s.monthly_salary)}/month · {LABELS[s.salary_method]} · {LABELS[s.schedule_type]}{s.schedule_type === "fixed_date" ? ` on day ${s.pay_day}` : ""}</div>
          <div className="text-xs text-stone-500">Joined {fmtDate(s.joining_date)}{s.leaving_date && ` · Left ${fmtDate(s.leaving_date)}`}{d.login_phone && ` · Login ${d.login_phone}`}</div>
        </div>
        <div className="flex flex-wrap gap-2">
          <button className="btn-outline btn-sm" onClick={() => setDlg("edit")} data-testid="profile-edit-btn"><Pencil className="h-3.5 w-3.5" /> Edit</button>
          {active && <>
            <button className="btn-outline btn-sm" onClick={() => { setAtt(null); setDlg("att"); }} data-testid="profile-attendance-btn"><CalendarX className="h-3.5 w-3.5" /> Attendance</button>
            <button className="btn-outline btn-sm" onClick={() => setDlg("advance")} data-testid="profile-advance-btn"><HandCoins className="h-3.5 w-3.5" /> Advance</button>
            <button className="btn-outline btn-sm" onClick={() => setDlg("fine")} data-testid="profile-fine-btn"><Gavel className="h-3.5 w-3.5" /> Fine</button>
            <button className="btn-outline btn-sm" onClick={() => setDlg("login")} data-testid="profile-login-btn"><KeyRound className="h-3.5 w-3.5" /> Login</button>
            {s.cycle_paused && <button className="btn-gold btn-sm" onClick={async () => { await api.post(`/staff/${id}/resume-cycle`); toast.success("Cycle resumed"); load(); }} data-testid="profile-resume-btn"><Play className="h-3.5 w-3.5" /> Resume cycle</button>}
            <button className="btn-primary btn-sm" onClick={() => setDlg("leave")} data-testid="profile-leave-btn"><LogOut className="h-3.5 w-3.5" /> Mark as Left</button>
          </>}
        </div>
      </div>

      {d.settlement && (
        <div className="card mb-5 border-[#8B1E2D]/30 p-5" data-testid="settlement-card">
          <h3 className="mb-2 font-semibold">Final settlement</h3>
          <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <div>Total net salary<div className="font-num font-semibold">{inr(d.settlement.net_total)}</div></div>
            <div>Total paid<div className="font-num font-semibold">{inr(d.settlement.paid_total)}</div></div>
            <div>Final balance due<div className="font-num font-semibold text-[#8B1E2D]">{inr(d.settlement.balance)}</div></div>
            <div>Advance outstanding<div className="font-num font-semibold">{inr(d.settlement.advance_outstanding)}</div></div>
          </div>
        </div>
      )}

      <div className="mb-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard tone="dark" label="Earned this month" value={d.this_month.earned} money hint={`${d.this_month.eligible_days} days · rate ${inr(d.this_month.daily_rate)}/day`} testid="profile-earned" />
        <StatCard label="Outstanding salary" value={d.outstanding} money testid="profile-outstanding" />
        <StatCard label="Advance balance" value={d.advance_summary.outstanding} money hint={`Recovered this month ${inr(d.advance_summary.recovered_this_month)}`} testid="profile-advance-balance" />
        <StatCard label="Paid leave left" value={`${d.leave.remaining} / ${d.leave.quota}`} hint={`${d.leave.period}: ${d.leave.paid} paid, ${d.leave.unpaid} unpaid`} testid="profile-leave" />
      </div>

      <Tabs defaultValue="salary">
        <TabsList className="mb-3 flex w-full overflow-x-auto">
          {["salary", "attendance", "advances", "fines", "payments"].map((t) => <TabsTrigger key={t} value={t} className="flex-1 capitalize" data-testid={`profile-tab-${t}`}>{t}</TabsTrigger>)}
        </TabsList>
        <TabsContent value="salary">
          <List items={d.obligations} empty="No salary periods yet" testid="profile-obligations" render={(v) => (
            <button key={v.id} onClick={() => setOid(v.id)} className="flex w-full items-center justify-between gap-3 p-4 text-left hover:bg-stone-50" data-testid="profile-obligation-row">
              <div><div className="font-medium">{fmtDate(v.period_start)} – {fmtDate(v.period_end)}</div><div className="text-xs text-stone-500">Due {fmtDate(v.due_date)} · Net {inr(v.net_payable)} · Paid {inr(v.paid)}</div></div>
              <div className="flex items-center gap-2"><span className="font-num text-sm font-semibold">{inr(v.balance)}</span><StatusBadge status={v.status} /></div>
            </button>
          )} />
        </TabsContent>
        <TabsContent value="attendance">
          <p className="mb-2 text-xs text-stone-500">All other days are Present by default.</p>
          <List items={d.attendance} empty="No exceptions recorded — always present" testid="profile-attendance" render={(a) => (
            <button key={a.date} onClick={() => { setAtt(a); setDlg("att"); }} className="flex w-full items-center justify-between p-3 text-left text-sm hover:bg-stone-50" data-testid="profile-attendance-row">
              <span>{fmtDate(a.date)} {a.note && <span className="text-xs text-stone-500">· {a.note}</span>}</span>
              <span className="flex items-center gap-2">{a.status === "late" && <span className="font-num text-xs">{a.hours_late}h · {inr(a.fine_amount)}</span>}<StatusBadge status={a.status} /></span>
            </button>
          )} />
        </TabsContent>
        <TabsContent value="advances">
          <List items={d.advances} empty="No advances" testid="profile-advances" render={(a) => (
            <div key={a.id} className="flex items-center justify-between gap-2 p-3 text-sm">
              <div><span className="font-num font-semibold">{inr(a.amount)}</span> <span className="text-xs text-stone-500">· {fmtDate(a.date)} {a.description && `· ${a.description}`}</span>{a.reversal_reason && <div className="text-xs text-red-700">Reversed: {a.reversal_reason}</div>}</div>
              <div className="flex items-center gap-2"><StatusBadge status={a.status === "active" ? "valid" : "reversed"} label={a.status} />{a.status === "active" && <button className="btn-outline btn-sm" onClick={() => setRev({ kind: "advances", item: a })} data-testid="advance-reverse-btn">Reverse</button>}</div>
            </div>
          )} />
          <h4 className="mb-2 mt-5 text-sm font-semibold">Salary recoveries (applied automatically, remaining balance carries forward)</h4>
          <List items={d.recoveries} empty="No recoveries yet" testid="profile-recoveries" render={(r) => (
            <div key={r.obligation_id} className="flex justify-between p-3 text-sm"><span>{fmtDate(r.period_start)} – {fmtDate(r.period_end)} <span className="text-xs text-stone-500">· {r.mode === "auto" ? "scheduled" : "recorded"}</span></span><span className="font-num">{inr(r.amount)}</span></div>
          )} />
        </TabsContent>
        <TabsContent value="fines">
          <List items={d.fines} empty="No manual fines" testid="profile-fines" render={(f) => (
            <div key={f.id} className="flex items-center justify-between gap-2 p-3 text-sm">
              <div><span className="font-num font-semibold">{inr(f.amount)}</span> <span className="text-xs text-stone-500">· {fmtDate(f.date)} · {f.reason}</span>{f.reversal_reason && <div className="text-xs text-red-700">Reversed: {f.reversal_reason}</div>}</div>
              <div className="flex items-center gap-2"><StatusBadge status={f.status === "active" ? "valid" : "reversed"} label={f.status} />{f.status === "active" && <button className="btn-outline btn-sm" onClick={() => setRev({ kind: "fines", item: f })} data-testid="fine-reverse-btn">Reverse</button>}</div>
            </div>
          )} />
        </TabsContent>
        <TabsContent value="payments">
          <List items={d.transactions} empty="No payments yet" testid="profile-payments" render={(t) => (
            <button key={t.id} onClick={() => setOid(t.obligation_id)} className="flex w-full items-center justify-between p-3 text-left text-sm hover:bg-stone-50">
              <span>{fmtDate(t.date)} · {LABELS[t.method]} <span className="text-xs text-stone-500">for {fmtDate(t.period_start)} – {fmtDate(t.period_end)}</span></span>
              <span className="flex items-center gap-2"><span className="font-num font-semibold">{inr(t.amount)}</span><StatusBadge status={t.status} /></span>
            </button>
          )} />
        </TabsContent>
      </Tabs>

      <StaffFormDialog open={dlg === "edit"} onOpenChange={close} staff={s} onSaved={load} />
      <AttendanceDialog open={dlg === "att"} onOpenChange={close} staffId={id} date={att?.date} existing={att} onSaved={load} />
      <EntryDialog kind="advance" open={dlg === "advance"} onOpenChange={close} staffId={id} onSaved={load} />
      <EntryDialog kind="fine" open={dlg === "fine"} onOpenChange={close} staffId={id} onSaved={load} />
      <LeaveDialog open={dlg === "leave"} onOpenChange={close} staff={s} onDone={load} />
      <LoginDialog open={dlg === "login"} onOpenChange={close} staff={s} current={d.login_phone} onDone={load} />
      <ObligationDialog oid={oid} onOpenChange={(o) => !o && setOid(null)} onChanged={load} />
      <ConfirmDialog open={!!rev} onOpenChange={(o) => !o && setRev(null)} danger requireReason confirmLabel="Reverse"
        title={`Reverse this ${rev?.kind === "fines" ? "fine" : "advance"}?`} description={rev && `${inr(rev.item.amount)} on ${fmtDate(rev.item.date)}. The record stays in history as reversed.`}
        onConfirm={async (reason) => {
          try { await api.post(`/${rev.kind}/${rev.item.id}/reverse`, { reason }); toast.success("Reversed"); load(); } catch (e) { toast.error(errMsg(e)); }
        }} />
    </div>
  );
}
