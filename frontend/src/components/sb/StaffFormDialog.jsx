import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { api, errMsg, todayISO } from "@/lib/api";
import { Field, ErrorBox } from "@/components/sb/Kit";
import { ImageInput } from "@/components/sb/ImageInput";
import { useAuth } from "@/context/AuthContext";

const blank = (d = {}) => ({
  name: "", phone: "", designation: "", monthly_salary: "", joining_date: todayISO(),
  salary_method: d.salary_method || "fixed30", schedule_type: d.schedule_type || "fixed_date",
  pay_day: d.pay_day || 1, cycle_start: "", photo: null,
});

export const ScheduleFields = ({ f, set, showCycle = true }) => (
  <>
    <Field label="Salary calculation">
      <select className="inp" value={f.salary_method} onChange={(e) => set("salary_method", e.target.value)} data-testid="salary-method-select">
        <option value="fixed30">Fixed 30 days (salary ÷ 30)</option>
        <option value="calendar">Calendar days (salary ÷ days in month)</option>
      </select>
    </Field>
    <Field label="Payment schedule">
      <select className="inp" value={f.schedule_type} onChange={(e) => set("schedule_type", e.target.value)} data-testid="schedule-type-select">
        <option value="fixed_date">Fixed monthly date</option>
        <option value="cycle30">30-day cycle</option>
        <option value="cycle40">40-day cycle</option>
      </select>
    </Field>
    {f.schedule_type === "fixed_date" ? (
      <Field label="Payment date (day of month)" hint="If the month is shorter, the last day of that month is used.">
        <input type="number" min={1} max={31} className="inp" value={f.pay_day} onChange={(e) => set("pay_day", e.target.value)} data-testid="pay-day-input" />
      </Field>
    ) : showCycle ? (
      <Field label="Cycle start date (optional)" hint="Defaults to the joining date.">
        <input type="date" className="inp" value={f.cycle_start || ""} onChange={(e) => set("cycle_start", e.target.value)} data-testid="cycle-start-input" />
      </Field>
    ) : null}
  </>
);

export function StaffFormDialog({ open, onOpenChange, staff, onSaved }) {
  const { business } = useAuth();
  const [defaults, setDefaults] = useState({});
  const [f, setF] = useState(blank());
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    setErr("");
    if (staff) {
      setF({ ...blank(), ...staff, photo: staff.photo ?? null, cycle_start: staff.cycle_start || "" });
    } else {
      api.get("/business").then((r) => { setDefaults(r.data.settings); setF(blank(r.data.settings)); }).catch(() => setF(blank(defaults)));
    }
  }, [open, staff]); // eslint-disable-line react-hooks/exhaustive-deps
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    const body = { ...f, monthly_salary: Number(f.monthly_salary), pay_day: Number(f.pay_day), cycle_start: f.cycle_start || null };
    try {
      const { data } = staff ? await api.put(`/staff/${staff.id}`, body) : await api.post("/staff", body);
      toast.success(staff ? "Staff updated" : "Staff added");
      onOpenChange(false);
      onSaved?.(data);
    } catch (ex) {
      setErr(errMsg(ex));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[92vh] overflow-y-auto sm:max-w-xl" data-testid="staff-form-dialog">
        <DialogHeader><DialogTitle>{staff ? "Edit staff" : `Add staff to ${business?.name || "business"}`}</DialogTitle></DialogHeader>
        <form onSubmit={save} className="grid gap-4 sm:grid-cols-2">
          <div className="sm:col-span-2"><ImageInput value={f.photo} onChange={(v) => set("photo", v)} label="Profile photo" testid="staff-photo" /></div>
          <Field label="Full name"><input className="inp" required value={f.name} onChange={(e) => set("name", e.target.value)} data-testid="staff-name-input" /></Field>
          <Field label="Designation"><input className="inp" value={f.designation} onChange={(e) => set("designation", e.target.value)} placeholder="e.g. Cashier" data-testid="staff-designation-input" /></Field>
          <Field label="Monthly fixed salary (₹)"><input type="number" min="1" step="0.01" className="inp" required value={f.monthly_salary} onChange={(e) => set("monthly_salary", e.target.value)} data-testid="staff-salary-input" /></Field>
          <Field label="Joining date"><input type="date" className="inp" required value={f.joining_date} onChange={(e) => set("joining_date", e.target.value)} data-testid="staff-joining-input" /></Field>
          <Field label="Mobile (optional)"><input className="inp" value={f.phone} onChange={(e) => set("phone", e.target.value)} placeholder="10-digit number" data-testid="staff-phone-input" /></Field>
          <ScheduleFields f={f} set={set} />
          {staff && <p className="text-xs text-stone-500 sm:col-span-2">Salary and schedule changes apply from the next salary period. Past periods keep their original salary.</p>}
          <div className="sm:col-span-2"><ErrorBox error={err} /></div>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <button type="button" className="btn-outline" onClick={() => onOpenChange(false)}>Cancel</button>
            <button className="btn-primary" disabled={busy} data-testid="staff-form-submit">{busy ? "Saving…" : staff ? "Save changes" : "Add staff"}</button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
