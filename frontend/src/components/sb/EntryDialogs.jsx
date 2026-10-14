import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, errMsg, todayISO } from "@/lib/api";
import { Field, ErrorBox } from "@/components/sb/Kit";
import { useStaffOptions, StaffSelect } from "@/components/sb/staffOptions";

const STATUSES = [["absent", "Absent"], ["half_day", "Half Day"], ["paid_leave", "Paid Leave"], ["late", "Late"]];

export function AttendanceDialog({ open, onOpenChange, staffId, date, existing, defaultStatus = "absent", onSaved }) {
  const options = useStaffOptions(open && !staffId);
  const [f, setF] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (open) {
      setErr("");
      setF({ staff_id: staffId || "", date: date || todayISO(), status: defaultStatus === "late" ? "late" : existing?.status || defaultStatus, hours_late: existing?.hours_late || "", note: existing?.note || "" });
    }
  }, [open, staffId, date, existing, defaultStatus]);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      await api.put("/attendance", { ...f, hours_late: Number(f.hours_late || 0) });
      toast.success("Attendance saved");
      onOpenChange(false);
      onSaved?.();
    } catch (ex) {
      setErr(errMsg(ex));
    } finally {
      setBusy(false);
    }
  };
  const clear = async () => {
    setBusy(true);
    try {
      await api.delete(`/attendance/${f.staff_id}/${f.date}`);
      toast.success("Marked present");
      onOpenChange(false);
      onSaved?.();
    } catch (ex) {
      setErr(errMsg(ex));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="attendance-dialog">
        <DialogHeader><DialogTitle>{existing ? "Edit attendance" : "Mark attendance exception"}</DialogTitle></DialogHeader>
        <p className="-mt-2 text-xs text-stone-500">Everyone is Present by default. Record only exceptions.</p>
        <form onSubmit={submit} className="grid gap-4">
          {!staffId && <Field label="Staff"><StaffSelect value={f.staff_id} onChange={(v) => set("staff_id", v)} options={options} testid="attendance-staff-select" /></Field>}
          <Field label="Date"><input type="date" className="inp" value={f.date || ""} onChange={(e) => set("date", e.target.value)} required disabled={!!existing} data-testid="attendance-date-input" /></Field>
          <div>
            <span className="lbl">Status</span>
            <div className="grid grid-cols-2 gap-2">
              {STATUSES.map(([k, l]) => (
                <button type="button" key={k} onClick={() => set("status", k)} data-testid={`attendance-status-${k}`}
                  className={`rounded-lg border px-3 py-2.5 text-sm font-medium ${f.status === k ? "border-[#8B1E2D] bg-[#8B1E2D] text-white" : "border-stone-300 bg-white"}`}>{l}</button>
              ))}
            </div>
          </div>
          {f.status === "late" && (
            <Field label="Hours late" hint="Fine = hours late × your hourly late-fine rate"><input type="number" min="0.25" step="0.25" max="24" className="inp" value={f.hours_late} onChange={(e) => set("hours_late", e.target.value)} required data-testid="attendance-hours-input" /></Field>
          )}
          <Field label="Note (optional)"><input className="inp" value={f.note || ""} onChange={(e) => set("note", e.target.value)} data-testid="attendance-note-input" /></Field>
          <ErrorBox error={err} />
          <div className="flex flex-wrap justify-end gap-2">
            {existing && <button type="button" className="btn-outline" onClick={clear} disabled={busy} data-testid="attendance-clear-btn">Mark Present</button>}
            <button className="btn-primary" disabled={busy || !f.staff_id} data-testid="attendance-submit-btn">{busy ? "Saving…" : "Save"}</button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function EntryDialog({ kind, open, onOpenChange, staffId, onSaved }) {
  const options = useStaffOptions(open && !staffId);
  const [f, setF] = useState({});
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const isFine = kind === "fine";
  useEffect(() => {
    if (open) {
      setErr("");
      setF({ staff_id: staffId || "", amount: "", date: todayISO(), text: "" });
    }
  }, [open, staffId]);
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    const body = { staff_id: f.staff_id, amount: Number(f.amount), date: f.date, [isFine ? "reason" : "description"]: f.text };
    try {
      await api.post(isFine ? "/fines" : "/advances", body);
      toast.success(isFine ? "Fine added" : "Advance recorded");
      onOpenChange(false);
      onSaved?.();
    } catch (ex) {
      setErr(errMsg(ex));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid={`${kind}-dialog`}>
        <DialogHeader><DialogTitle>{isFine ? "Add manual fine" : "Add advance / loan"}</DialogTitle></DialogHeader>
        <p className="-mt-2 text-xs text-stone-500">{isFine ? "Deducted from the salary period that contains this date." : "Recovered from salary when you record a payment. Unrecovered balance carries forward."}</p>
        <form onSubmit={submit} className="grid gap-4">
          {!staffId && <Field label="Staff"><StaffSelect value={f.staff_id} onChange={(v) => set("staff_id", v)} options={options} testid={`${kind}-staff-select`} /></Field>}
          <div className="grid grid-cols-2 gap-3">
            <Field label="Amount (₹)"><input type="number" min="1" step="0.01" className="inp" required value={f.amount} onChange={(e) => set("amount", e.target.value)} data-testid={`${kind}-amount-input`} /></Field>
            <Field label="Date"><input type="date" className="inp" required value={f.date} onChange={(e) => set("date", e.target.value)} data-testid={`${kind}-date-input`} /></Field>
          </div>
          <Field label={isFine ? "Reason" : "Description (optional)"}><input className="inp" required={isFine} minLength={isFine ? 2 : 0} value={f.text} onChange={(e) => set("text", e.target.value)} data-testid={`${kind}-text-input`} /></Field>
          <ErrorBox error={err} />
          <div className="flex justify-end"><button className="btn-primary" disabled={busy || !f.staff_id} data-testid={`${kind}-submit-btn`}>{busy ? "Saving…" : "Save"}</button></div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
