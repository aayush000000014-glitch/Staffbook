import { useEffect, useState } from "react";
import { toast } from "sonner";
import { api, errMsg, fmtDate, BUSINESS_TYPES } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { PageHeader, Loader, Field, ErrorBox } from "@/components/sb/Kit";
import { ImageInput } from "@/components/sb/ImageInput";
import { ScheduleFields } from "@/components/sb/StaffFormDialog";
import { PolicyFields } from "@/pages/Onboarding";
import { ConfirmDialog } from "@/components/sb/ConfirmDialog";

const Section = ({ title, hint, children }) => (
  <section className="card p-5 sm:p-6">
    <h3 className="font-semibold">{title}</h3>
    {hint && <p className="mt-0.5 text-xs text-stone-500">{hint}</p>}
    <div className="mt-4 grid gap-4 sm:grid-cols-2">{children}</div>
  </section>
);

function AccountSection() {
  const [pw, setPw] = useState({ current_password: "", new_password: "" });
  const [sq, setSq] = useState({ current_password: "", security_question: "", security_answer: "" });
  const [err, setErr] = useState("");
  const run = async (path, body, reset) => {
    setErr("");
    try { await api.post(path, body); toast.success("Saved"); reset(); } catch (e) { setErr(errMsg(e)); }
  };
  return (
    <Section title="Account & security" hint="Change your password or the security question used for password recovery.">
      <Field label="Current password"><input type="password" className="inp" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} data-testid="pw-current-input" /></Field>
      <Field label="New password"><input type="password" className="inp" minLength={8} value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} data-testid="pw-new-input" /></Field>
      <div className="sm:col-span-2"><button className="btn-dark btn-sm" onClick={() => run("/auth/change-password", pw, () => setPw({ current_password: "", new_password: "" }))} data-testid="pw-save-btn">Change password</button></div>
      <Field label="New security question"><input className="inp" value={sq.security_question} onChange={(e) => setSq({ ...sq, security_question: e.target.value })} data-testid="sq-question-input" /></Field>
      <Field label="Answer"><input className="inp" value={sq.security_answer} onChange={(e) => setSq({ ...sq, security_answer: e.target.value })} data-testid="sq-answer-input" /></Field>
      <Field label="Current password"><input type="password" className="inp" value={sq.current_password} onChange={(e) => setSq({ ...sq, current_password: e.target.value })} data-testid="sq-password-input" /></Field>
      <div className="flex items-end"><button className="btn-dark btn-sm" onClick={() => run("/auth/security-question", sq, () => setSq({ current_password: "", security_question: "", security_answer: "" }))} data-testid="sq-save-btn">Update security question</button></div>
      <div className="sm:col-span-2"><ErrorBox error={err} /></div>
    </Section>
  );
}

function AuditSection() {
  const [rows, setRows] = useState(null);
  useEffect(() => { api.get("/audit").then((r) => setRows(r.data.slice(0, 40))); }, []);
  return (
    <section className="card p-5 sm:p-6">
      <h3 className="font-semibold">Audit log</h3>
      <p className="mt-0.5 text-xs text-stone-500">Last 40 changes in your business.</p>
      <div className="mt-3 max-h-80 overflow-y-auto text-xs" data-testid="audit-log">
        {!rows ? <Loader /> : rows.map((h) => (
          <div key={h.id} className="border-b border-stone-100 py-2"><span className="font-semibold">{h.action}</span> · {h.user_name} · {new Date(h.created_at).toLocaleString("en-IN")}</div>
        ))}
      </div>
    </section>
  );
}

export default function Settings() {
  const { refresh } = useAuth();
  const [b, setB] = useState(null);
  const [err, setErr] = useState("");
  const [confirm, setConfirm] = useState(false);
  useEffect(() => { api.get("/business").then((r) => setB(r.data)).catch((e) => setErr(errMsg(e))); }, []);
  if (!b) return err ? <ErrorBox error={err} /> : <Loader />;
  const setP = (k, v) => setB((x) => ({ ...x, [k]: v }));
  const setS = (k, v) => setB((x) => ({ ...x, settings: { ...x.settings, [k]: v } }));
  const save = async () => {
    setErr("");
    const s = b.settings;
    try {
      const { data } = await api.put("/business", {
        profile: { name: b.name, logo: b.logo, type: b.type || "", location: b.location || "" },
        settings: { ...s, pay_day: Number(s.pay_day), late_fine_per_hour: Number(s.late_fine_per_hour || 0), paid_leave_quota: Number(s.paid_leave_quota || 0), allow_future_attendance_days: Number(s.allow_future_attendance_days ?? 31) },
      });
      setB(data);
      await refresh();
      toast.success("Settings saved");
    } catch (e) {
      setErr(errMsg(e));
    }
  };
  return (
    <div className="grid gap-5" data-testid="settings-page">
      <PageHeader title="Settings" subtitle={`Registered ${fmtDate(b.created_at)} · ${b.active_staff_count} active staff`} />
      <Section title="Business profile" hint="Name, logo, type and location are the only details that may be shown publicly.">
        <div className="sm:col-span-2"><ImageInput value={b.logo} onChange={(v) => setP("logo", v)} label="Change logo" testid="settings-logo" /></div>
        <Field label="Business name"><input className="inp" value={b.name} onChange={(e) => setP("name", e.target.value)} data-testid="settings-name-input" /></Field>
        <Field label="Business type"><select className="inp" value={b.type} onChange={(e) => setP("type", e.target.value)} data-testid="settings-type-select">{[...new Set([b.type, ...BUSINESS_TYPES])].filter(Boolean).map((t) => <option key={t}>{t}</option>)}</select></Field>
        <div className="sm:col-span-2"><Field label="Location"><input className="inp" value={b.location} onChange={(e) => setP("location", e.target.value)} data-testid="settings-location-input" /></Field></div>
      </Section>
      <Section title="Salary & payment defaults" hint="Applied to new staff. Existing staff keep their own settings (edit them from the staff profile).">
        <ScheduleFields f={b.settings} set={setS} showCycle={false} />
      </Section>
      <Section title="Fines, leave & attendance rules" hint="Late-fine rate applies to late entries recorded after you change it.">
        <PolicyFields s={b.settings} set={setS} />
        <Field label="Allow attendance entries up to N days ahead"><input type="number" min="0" max="90" className="inp" value={b.settings.allow_future_attendance_days ?? 31} onChange={(e) => setS("allow_future_attendance_days", e.target.value)} data-testid="future-days-input" /></Field>
      </Section>
      <ErrorBox error={err} />
      <div className="flex justify-end"><button className="btn-primary" onClick={() => setConfirm(true)} data-testid="settings-save-btn">Save settings</button></div>
      <AccountSection />
      <AuditSection />
      <ConfirmDialog open={confirm} onOpenChange={setConfirm} title="Save business settings?" description="Changes to salary and leave policy affect calculations for open salary periods." onConfirm={save} />
    </div>
  );
}
