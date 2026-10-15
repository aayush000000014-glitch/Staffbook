import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Plus, Trash2, Check } from "lucide-react";
import { api, errMsg, todayISO, BUSINESS_TYPES } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Field, ErrorBox } from "@/components/sb/Kit";
import { ImageInput } from "@/components/sb/ImageInput";
import { ScheduleFields } from "@/components/sb/StaffFormDialog";

const STEPS = ["Business", "Owner", "Salary & payments", "Fines & leave", "Staff"];
const newStaff = () => ({ name: "", designation: "", monthly_salary: "", joining_date: todayISO() });

export const PolicyFields = ({ s, set }) => (
  <>
    <Field label="Late fine per hour (₹)" hint="Fine = hours late × this rate"><input type="number" min="0" step="0.01" className="inp" value={s.late_fine_per_hour} onChange={(e) => set("late_fine_per_hour", e.target.value)} data-testid="late-fine-input" /></Field>
    <Field label="Paid leave quota (days, max 5)"><input type="number" min="0" max="5" className="inp" value={s.paid_leave_quota} onChange={(e) => set("paid_leave_quota", e.target.value)} data-testid="leave-quota-input" /></Field>
    <Field label="Quota period" hint="Leave beyond the quota is unpaid (deducted at the daily rate).">
      <select className="inp" value={s.leave_quota_period} onChange={(e) => set("leave_quota_period", e.target.value)} data-testid="leave-period-select">
        <option value="monthly">Monthly</option><option value="yearly">Yearly</option>
      </select>
    </Field>
    <label className="flex items-start gap-2 text-sm sm:col-span-2">
      <input type="checkbox" className="mt-1 accent-[#8B1E2D]" checked={!!s.carry_forward_fines} onChange={(e) => set("carry_forward_fines", e.target.checked)} data-testid="carry-fines-checkbox" />
      <span>Carry forward fines that exceed a period's salary <span className="block text-xs text-stone-500">If off, fines above the earned salary are not deducted. Advances above salary always carry forward.</span></span>
    </label>
  </>
);

export default function Onboarding() {
  const { business, user, refresh } = useAuth();
  const nav = useNavigate();
  const [step, setStep] = useState(0);
  const [biz, setBiz] = useState({ name: business?.name || "", logo: null, type: BUSINESS_TYPES[0], location: "" });
  const [owner, setOwner] = useState({ name: user?.name || "", email: "" });
  const [s, setS] = useState({ salary_method: "fixed30", schedule_type: "fixed_date", pay_day: 10, late_fine_per_hour: 0, paid_leave_quota: 2, leave_quota_period: "monthly", carry_forward_fines: false });
  const [staff, setStaff] = useState([newStaff()]);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const setSet = (k, v) => setS((x) => ({ ...x, [k]: v }));
  const setRow = (i, k, v) => setStaff((rows) => rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));

  const finish = async () => {
    setBusy(true);
    setErr("");
    const rows = staff.filter((r) => r.name.trim());
    try {
      await api.post("/onboarding", {
        business: biz, owner: { name: owner.name, email: owner.email || null },
        settings: { ...s, pay_day: Number(s.pay_day), late_fine_per_hour: Number(s.late_fine_per_hour || 0), paid_leave_quota: Number(s.paid_leave_quota || 0), allow_future_attendance_days: 31 },
        staff: rows.map((r) => ({ ...r, monthly_salary: Number(r.monthly_salary) })),
      });
      await refresh();
      toast.success("Your business is ready");
      nav("/dashboard", { replace: true });
    } catch (ex) {
      setErr(errMsg(ex));
    } finally {
      setBusy(false);
    }
  };
  const next = (e) => { e.preventDefault(); if (step < STEPS.length - 1) setStep(step + 1); else finish(); };

  return (
    <div className="min-h-screen bg-[#F7F5F0] px-4 py-8 sm:py-12">
      <div className="mx-auto max-w-2xl">
        <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-[#8B1E2D]">Set up StaffBook · Step {step + 1} of {STEPS.length}</div>
        <h1 className="text-3xl font-bold tracking-tight">{STEPS[step]}</h1>
        <div className="mt-5 flex gap-1.5">
          {STEPS.map((x, i) => <div key={x} className={`h-1.5 flex-1 rounded-full ${i <= step ? "bg-[#8B1E2D]" : "bg-stone-300"}`} />)}
        </div>
        <form onSubmit={next} className="card mt-6 grid gap-4 p-5 sm:grid-cols-2 sm:p-7" data-testid={`onboarding-step-${step}`}>
          {step === 0 && (<>
            <div className="sm:col-span-2"><ImageInput value={biz.logo} onChange={(v) => setBiz({ ...biz, logo: v })} label="Upload logo" testid="onb-logo" /></div>
            <Field label="Business name"><input className="inp" required minLength={2} value={biz.name} onChange={(e) => setBiz({ ...biz, name: e.target.value })} data-testid="onb-name-input" /></Field>
            <Field label="Business type">
              <select className="inp" value={biz.type} onChange={(e) => setBiz({ ...biz, type: e.target.value })} data-testid="onb-type-select">{BUSINESS_TYPES.map((t) => <option key={t}>{t}</option>)}</select>
            </Field>
            <div className="sm:col-span-2"><Field label="Location"><input className="inp" required value={biz.location} onChange={(e) => setBiz({ ...biz, location: e.target.value })} placeholder="e.g. Karol Bagh, New Delhi" data-testid="onb-location-input" /></Field></div>
          </>)}
          {step === 1 && (<>
            <Field label="Owner name"><input className="inp" required minLength={2} value={owner.name} onChange={(e) => setOwner({ ...owner, name: e.target.value })} data-testid="onb-owner-name-input" /></Field>
            <Field label="Email (optional)"><input type="email" className="inp" value={owner.email} onChange={(e) => setOwner({ ...owner, email: e.target.value })} data-testid="onb-owner-email-input" /></Field>
            <div className="text-sm text-stone-600 sm:col-span-2">Login mobile: <span className="font-num">{user?.phone}</span></div>
          </>)}
          {step === 2 && (<>
            <ScheduleFields f={s} set={setSet} showCycle={false} />
            <p className="text-xs text-stone-500 sm:col-span-2">These are defaults for new staff. Each staff member can have their own method and schedule. Example: joining 13 Oct with payment date 10 → first payment due 10 Nov.</p>
          </>)}
          {step === 3 && <PolicyFields s={s} set={setSet} />}
          {step === 4 && (
            <div className="grid gap-3 sm:col-span-2">
              <p className="text-sm text-stone-600">Add your current staff now (optional). You can add more later.</p>
              {staff.map((r, i) => (
                <div key={i} className="grid gap-2 rounded-lg border border-stone-200 p-3 sm:grid-cols-[1.4fr_1fr_1fr_1fr_auto]" data-testid={`onb-staff-row-${i}`}>
                  <input className="inp" placeholder="Full name" value={r.name} onChange={(e) => setRow(i, "name", e.target.value)} data-testid={`onb-staff-name-${i}`} />
                  <input className="inp" placeholder="Designation" value={r.designation} onChange={(e) => setRow(i, "designation", e.target.value)} data-testid={`onb-staff-designation-${i}`} />
                  <input className="inp" type="number" min="1" placeholder="Salary ₹" required={!!r.name} value={r.monthly_salary} onChange={(e) => setRow(i, "monthly_salary", e.target.value)} data-testid={`onb-staff-salary-${i}`} />
                  <input className="inp" type="date" value={r.joining_date} onChange={(e) => setRow(i, "joining_date", e.target.value)} data-testid={`onb-staff-joining-${i}`} />
                  <button type="button" className="btn-ghost btn-sm" onClick={() => setStaff(staff.filter((_, j) => j !== i))} aria-label="Remove"><Trash2 className="h-4 w-4" /></button>
                </div>
              ))}
              <button type="button" className="btn-outline w-fit" onClick={() => setStaff([...staff, newStaff()])} data-testid="onb-add-staff-row"><Plus className="h-4 w-4" /> Add another</button>
            </div>
          )}
          <div className="sm:col-span-2"><ErrorBox error={err} /></div>
          <div className="flex justify-between sm:col-span-2">
            <button type="button" className="btn-outline" disabled={step === 0} onClick={() => setStep(step - 1)} data-testid="onb-back-btn">Back</button>
            <button className="btn-primary" disabled={busy} data-testid="onb-next-btn">{step === STEPS.length - 1 ? (<><Check className="h-4 w-4" /> {busy ? "Saving…" : "Finish setup"}</>) : "Continue"}</button>
          </div>
        </form>
      </div>
    </div>
  );
}
