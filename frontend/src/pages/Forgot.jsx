import { useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { api, errMsg } from "@/lib/api";
import { AuthShell, PhoneInput } from "@/components/sb/AuthShell";
import { Field, ErrorBox } from "@/components/sb/Kit";

export default function Forgot() {
  const [phone, setPhone] = useState("");
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [pw, setPw] = useState("");
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const run = async (fn) => {
    setBusy(true);
    setErr("");
    try { await fn(); } catch (ex) { setErr(errMsg(ex)); } finally { setBusy(false); }
  };
  const getQ = (e) => { e.preventDefault(); run(async () => setQuestion((await api.post("/auth/recovery/question", { phone })).data.question)); };
  const reset = (e) => {
    e.preventDefault();
    run(async () => { await api.post("/auth/recovery/reset", { phone, answer, new_password: pw }); setDone(true); toast.success("Password updated"); });
  };
  return (
    <AuthShell title="Reset password" subtitle="Answer your security question to set a new password. Staff accounts are reset by the business owner.">
      {done ? (
        <div className="grid gap-4" data-testid="reset-done">
          <div className="rounded-lg bg-emerald-50 p-4 text-sm text-emerald-800">Your password has been updated.</div>
          <Link to="/login" className="btn-primary" data-testid="reset-login-link">Go to login</Link>
        </div>
      ) : !question ? (
        <form onSubmit={getQ} className="grid gap-4">
          <Field label="Mobile number"><PhoneInput value={phone} onChange={setPhone} testid="forgot-phone-input" /></Field>
          <ErrorBox error={err} />
          <button className="btn-primary w-full py-3" disabled={busy} data-testid="forgot-next-btn">Continue</button>
          <Link to="/login" className="text-center text-sm hover:underline">Back to login</Link>
        </form>
      ) : (
        <form onSubmit={reset} className="grid gap-4">
          <div className="rounded-lg border border-stone-200 bg-white p-3 text-sm" data-testid="forgot-question">{question}</div>
          <Field label="Your answer"><input className="inp" required value={answer} onChange={(e) => setAnswer(e.target.value)} data-testid="forgot-answer-input" /></Field>
          <Field label="New password" hint="At least 8 characters"><input type="password" className="inp" required minLength={8} value={pw} onChange={(e) => setPw(e.target.value)} data-testid="forgot-newpw-input" /></Field>
          <ErrorBox error={err} />
          <button className="btn-primary w-full py-3" disabled={busy} data-testid="forgot-reset-btn">Reset password</button>
        </form>
      )}
    </AuthShell>
  );
}
