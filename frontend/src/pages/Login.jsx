import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, errMsg } from "@/lib/api";
import { useAuth, homeFor } from "@/context/AuthContext";
import { AuthShell, PhoneInput } from "@/components/sb/AuthShell";
import { Field, ErrorBox } from "@/components/sb/Kit";

export default function Login() {
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const { signIn } = useAuth();
  const nav = useNavigate();
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setErr("");
    try {
      const { data } = await api.post("/auth/login", { phone, password });
      await signIn(data.token);
      nav(homeFor(data.user, { onboarded: true }), { replace: true });
    } catch (ex) {
      setErr(errMsg(ex));
    } finally {
      setBusy(false);
    }
  };
  return (
    <AuthShell title="Welcome back" subtitle="Log in with your mobile number and password.">
      <form onSubmit={submit} className="grid gap-4" data-testid="login-form">
        <Field label="Mobile number"><PhoneInput value={phone} onChange={setPhone} testid="login-phone-input" /></Field>
        <Field label="Password"><input type="password" className="inp" required value={password} onChange={(e) => setPassword(e.target.value)} data-testid="login-password-input" /></Field>
        <ErrorBox error={err} />
        <button className="btn-primary w-full py-3" disabled={busy} data-testid="login-submit-btn">{busy ? "Logging in…" : "Log in"}</button>
        <div className="flex justify-between text-sm">
          <Link to="/forgot" className="text-[#8B1E2D] hover:underline" data-testid="forgot-link">Forgot password?</Link>
          <Link to="/signup" className="font-semibold hover:underline" data-testid="signup-link">Create business account</Link>
        </div>
      </form>
    </AuthShell>
  );
}
