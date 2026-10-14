import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { api, errMsg, inr, fmtDate, todayISO, newRef, LABELS } from "@/lib/api";
import { Field, ErrorBox, Loader, Row, StatusBadge } from "@/components/sb/Kit";
import { ConfirmDialog } from "@/components/sb/ConfirmDialog";

export const Breakdown = ({ v }) => {
  const b = v.breakdown;
  return (
    <div className="rounded-xl border border-stone-200 bg-stone-50 p-4" data-testid="salary-breakdown">
      <Row k={`Gross for ${b.eligible_days} eligible days (${LABELS[v.salary_method]})`} v={inr(b.gross)} />
      <Row k={`Attendance deduction (${b.absent_days} absent, ${b.half_days} half, ${b.unpaid_leave_days} unpaid leave)`} v={`− ${inr(b.attendance_deduction)}`} neg />
      <Row k="Earned salary" v={inr(b.earned)} strong />
      <Row k={`Late fines (${b.late_hours} hrs)`} v={`− ${inr(b.late_fines)}`} neg />
      <Row k="Manual fines" v={`− ${inr(v.manual_fines)}`} neg />
      <Row k="Advance recovery" v={`− ${inr(v.advance_recovery)}`} neg />
      <Row k="Other deductions" v={`− ${inr(v.other_deductions)}`} neg />
      <Row k="Net payable" v={inr(v.net_payable)} strong />
      <Row k="Paid so far" v={inr(v.paid)} />
      <Row k="Outstanding balance" v={inr(v.balance)} strong />
      {v.overpaid > 0 && <Row k="Overpaid" v={inr(v.overpaid)} neg />}
      <div className="mt-2 text-xs text-stone-500">Paid leave used: {b.paid_leave_days} day(s). Daily rate {inr(b.daily_rate)}. {v.accruing && "Period in progress — amounts are earned till today."}</div>
    </div>
  );
};

function PayForm({ d, oid, onDone }) {
  const [f, setF] = useState({ amount: d.balance || "", method: "cash", date: todayISO(), note: "", advance_recovery: d.advance_recovery, renew: true });
  const [ref] = useState(newRef());
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await api.post(`/obligations/${oid}/pay`, { ...f, amount: Number(f.amount), advance_recovery: Number(f.advance_recovery || 0), client_ref: ref });
      toast.success("Payment recorded");
      onDone(true);
    } catch (ex) {
      setErr(errMsg(ex));
    } finally {
      setBusy(false);
    }
  };
  if (d.balance <= 0) return <div className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800">Nothing outstanding for this period.</div>;
  return (
    <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" data-testid="pay-form">
      {d.advance_outstanding + d.advance_recovery > 0 && (
        <Field label="Recover from advance (₹)" hint={`Outstanding advance: ${inr(d.advance_outstanding)}. Balance updates after saving.`}>
          <input type="number" min="0" step="0.01" className="inp" value={f.advance_recovery} onChange={(e) => set("advance_recovery", e.target.value)} data-testid="pay-advance-recovery-input" />
        </Field>
      )}
      <Field label="Amount paid (₹)" hint={`Outstanding: ${inr(d.balance)}`}>
        <input type="number" min="0.01" step="0.01" className="inp" required value={f.amount} onChange={(e) => set("amount", e.target.value)} data-testid="pay-amount-input" />
      </Field>
      <Field label="Method">
        <select className="inp" value={f.method} onChange={(e) => set("method", e.target.value)} data-testid="pay-method-select">
          <option value="cash">Cash</option><option value="upi">UPI</option><option value="bank">Bank Transfer</option>
        </select>
      </Field>
      <Field label="Payment date"><input type="date" className="inp" max={todayISO()} required value={f.date} onChange={(e) => set("date", e.target.value)} data-testid="pay-date-input" /></Field>
      <Field label="Note (optional)"><input className="inp" value={f.note} onChange={(e) => set("note", e.target.value)} data-testid="pay-note-input" /></Field>
      <label className="flex items-start gap-2 text-sm sm:col-span-2">
        <input type="checkbox" className="mt-1 accent-[#8B1E2D]" checked={f.renew} onChange={(e) => set("renew", e.target.checked)} data-testid="pay-renew-checkbox" />
        <span>Automatically continue the next payment cycle <span className="block text-xs text-stone-500">Uncheck to record this payment without renewing the cycle (you can resume later from the staff profile).</span></span>
      </label>
      <div className="sm:col-span-2"><ErrorBox error={err} /></div>
      <div className="flex justify-end sm:col-span-2"><button className="btn-primary" disabled={busy} data-testid="pay-submit-btn">{busy ? "Saving…" : "Mark Payment Given"}</button></div>
    </form>
  );
}

function CorrectionForms({ d, oid, onDone }) {
  const [adj, setAdj] = useState({ advance_recovery: d.advance_recovery, other_deductions: d.other_deductions, reason: "" });
  const [due, setDue] = useState({ due_date: d.due_date, reason: "" });
  const [err, setErr] = useState("");
  const post = async (path, body, msg) => {
    setErr("");
    try {
      await api.post(path, body);
      toast.success(msg);
      onDone(false);
    } catch (ex) {
      setErr(errMsg(ex));
    }
  };
  return (
    <div className="grid gap-5">
      <div className="grid gap-3 rounded-xl border border-stone-200 p-4 sm:grid-cols-2">
        <div className="font-semibold sm:col-span-2">Adjust deductions</div>
        <Field label="Advance recovery (₹)"><input type="number" min="0" step="0.01" className="inp" value={adj.advance_recovery} onChange={(e) => setAdj({ ...adj, advance_recovery: e.target.value })} data-testid="adjust-advance-input" /></Field>
        <Field label="Other deductions (₹)"><input type="number" min="0" step="0.01" className="inp" value={adj.other_deductions} onChange={(e) => setAdj({ ...adj, other_deductions: e.target.value })} data-testid="adjust-other-input" /></Field>
        <div className="sm:col-span-2"><Field label="Reason"><input className="inp" value={adj.reason} onChange={(e) => setAdj({ ...adj, reason: e.target.value })} data-testid="adjust-reason-input" /></Field></div>
        <div className="sm:col-span-2 flex justify-end"><button className="btn-dark btn-sm" disabled={adj.reason.length < 3} data-testid="adjust-submit-btn"
          onClick={() => post(`/obligations/${oid}/adjust`, { advance_recovery: Number(adj.advance_recovery || 0), other_deductions: Number(adj.other_deductions || 0), reason: adj.reason }, "Deductions updated")}>Save adjustment</button></div>
      </div>
      <div className="grid gap-3 rounded-xl border border-stone-200 p-4 sm:grid-cols-2">
        <div className="font-semibold sm:col-span-2">Correct due date <span className="text-xs font-normal text-stone-500">(original {fmtDate(d.original_due_date)})</span></div>
        <Field label="New due date"><input type="date" className="inp" value={due.due_date} onChange={(e) => setDue({ ...due, due_date: e.target.value })} data-testid="due-date-input" /></Field>
        <Field label="Reason"><input className="inp" value={due.reason} onChange={(e) => setDue({ ...due, reason: e.target.value })} data-testid="due-reason-input" /></Field>
        <div className="sm:col-span-2 flex justify-end"><button className="btn-dark btn-sm" disabled={due.reason.length < 3} onClick={() => post(`/obligations/${oid}/due-date`, due, "Due date updated")} data-testid="due-submit-btn">Update due date</button></div>
      </div>
      <ErrorBox error={err} />
    </div>
  );
}

function History({ d, onDone }) {
  const [rev, setRev] = useState(null);
  return (
    <div className="grid gap-4">
      <div>
        <div className="mb-2 font-semibold">Transactions</div>
        {d.transactions.length === 0 && <div className="text-sm text-stone-500">No payments recorded yet.</div>}
        {d.transactions.map((t) => (
          <div key={t.id} className="mb-2 flex items-center justify-between gap-2 rounded-lg border border-stone-200 p-3 text-sm" data-testid="txn-row">
            <div>
              <div className="font-num font-semibold">{inr(t.amount)} <span className="font-sans text-xs font-normal text-stone-500">· {LABELS[t.method]} · {fmtDate(t.date)}</span></div>
              {t.note && <div className="text-xs text-stone-500">{t.note}</div>}
              {t.reversal_reason && <div className="text-xs text-red-700">Reversed: {t.reversal_reason}</div>}
            </div>
            <div className="flex items-center gap-2">
              <StatusBadge status={t.status} />
              {t.status === "valid" && <button className="btn-outline btn-sm" onClick={() => setRev(t)} data-testid="txn-reverse-btn">Reverse</button>}
            </div>
          </div>
        ))}
      </div>
      <div>
        <div className="mb-2 font-semibold">Audit history</div>
        {d.history.map((h) => (
          <div key={h.id} className="border-b border-stone-100 py-2 text-xs"><span className="font-semibold">{h.action}</span> · {h.user_name} · {new Date(h.created_at).toLocaleString("en-IN")}
            <div className="text-stone-500">{JSON.stringify(h.details)}</div></div>
        ))}
      </div>
      <ConfirmDialog open={!!rev} onOpenChange={(o) => !o && setRev(null)} title="Reverse this payment?" danger requireReason confirmLabel="Reverse payment"
        description={rev && `${inr(rev.amount)} on ${fmtDate(rev.date)} will be marked reversed. The record stays in history.`}
        onConfirm={async (reason) => {
          try { await api.post(`/transactions/${rev.id}/reverse`, { reason }); toast.success("Payment reversed"); onDone(false); } catch (ex) { toast.error(errMsg(ex)); }
        }} />
    </div>
  );
}

export function ObligationDialog({ oid, onOpenChange, onChanged }) {
  const [d, setD] = useState(null);
  const load = useCallback(() => {
    if (oid) api.get(`/obligations/${oid}`).then((r) => setD(r.data)).catch((e) => toast.error(errMsg(e)));
  }, [oid]);
  useEffect(() => {
    setD(null);
    load();
  }, [load]);
  const done = (close) => {
    onChanged?.();
    if (close) onOpenChange(false);
    else load();
  };
  return (
    <Dialog open={!!oid} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-2xl" data-testid="obligation-dialog">
        <DialogHeader><DialogTitle>{d ? `${d.staff_name} · Salary` : "Payment record"}</DialogTitle></DialogHeader>
        {!d ? <Loader /> : (
          <div className="grid gap-4">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <StatusBadge status={d.status} testid="obligation-status" />
              <span className="text-stone-600">Period {fmtDate(d.period_start)} – {fmtDate(d.period_end)}</span>
              <span className="text-stone-600">· Due {fmtDate(d.due_date)}</span>
            </div>
            <Breakdown v={d} />
            <Tabs defaultValue="pay">
              <TabsList className="w-full">
                <TabsTrigger value="pay" className="flex-1" data-testid="obl-tab-pay">Pay</TabsTrigger>
                <TabsTrigger value="correct" className="flex-1" data-testid="obl-tab-correct">Corrections</TabsTrigger>
                <TabsTrigger value="history" className="flex-1" data-testid="obl-tab-history">History</TabsTrigger>
              </TabsList>
              <TabsContent value="pay" className="pt-3"><PayForm key={`${d.balance}-${d.advance_recovery}`} d={d} oid={oid} onDone={done} /></TabsContent>
              <TabsContent value="correct" className="pt-3"><CorrectionForms key={d.due_date + d.other_deductions} d={d} oid={oid} onDone={done} /></TabsContent>
              <TabsContent value="history" className="pt-3"><History d={d} onDone={done} /></TabsContent>
            </Tabs>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
