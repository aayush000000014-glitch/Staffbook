import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errMsg } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { AuthShell, PhoneInput } from "@/components/sb/AuthShell";
import { Field, ErrorBox } from "@/components/sb/Kit";

const QUESTIONS = ["What was the name of your first school?", "What is your mother's village or hometown?", "What was the name of your first shop or employer?", "What is your favourite childhood dish?"];

export default function Signup() {
  const [f, setF] = useState({ name: "", phone: "", password: "", business_name: "", security_question: QUESTIONS[0], security_answer: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const { signIn } = useAuth();
  const nav = useNavigate();
  const set = (k, v) => setF((x) => ({ ...x, [k]: v }));
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const { data } = await api.post("/auth/signup", f);
      await signIn(data.token);
      nav("/onboarding", { replace: true });
    } catch (ex) {
      setErr(errMsg(ex));
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthShell title="Create your business account" subtitle="Free to start. You can add up to 100 active staff.">
      <form onSubmit={submit} className="grid gap-4" data-testid="signup-form">
        <Field label="Your name"><input className="inp" required minLength={2} value={f.name} onChange={(e) => set("name", e.target.value)} data-testid="signup-name-input" /></Field>
        <Field label="Business name"><input className="inp" required minLength={2} value={f.business_name} onChange={(e) => set("business_name", e.target.value)} data-testid="signup-business-input" /></Field>
        <Field label="Mobile number"><PhoneInput value={f.phone} onChange={(v) => set("phone", v)} testid="signup-phone-input" /></Field>
        <Field label="Password" hint="At least 8 characters"><input type="password" className="inp" required minLength={8} value={f.password} onChange={(e) => set("password", e.target.value)} data-testid="signup-password-input" /></Field>
        <Field label="Security question (for password recovery)">
          <select className="inp" value={f.security_question} onChange={(e) => set("security_question", e.target.value)} data-testid="signup-question-select">
            {QUESTIONS.map((q) => <option key={q}>{q}</option>)}
          </select>
        </Field>
        <Field label="Answer" hint="Not case-sensitive. Keep it memorable — it is the only way to reset your password."><input className="inp" required minLength={2} value={f.security_answer} onChange={(e) => set("security_answer", e.target.value)} data-testid="signup-answer-input" /></Field>
        <ErrorBox error={err} />
        <button className="btn-primary w-full py-3" disabled={busy} data-testid="signup-submit-btn">{busy ? "Creating…" : "Create account"}</button>
        <div className="text-center text-sm">Already have an account? <Link to="/login" className="font-semibold text-[#8B1E2D] hover:underline" data-testid="login-link">Log in</Link></div>
      </form>
    </AuthShell>
  );
}
