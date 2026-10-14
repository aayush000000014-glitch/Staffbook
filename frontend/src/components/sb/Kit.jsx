import { Loader2, Inbox } from "lucide-react";
import { LABELS, inr } from "@/lib/api";

export const PageHeader = ({ title, subtitle, actions, testid }) => (
  <div className="mb-6 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between" data-testid={testid}>
    <div>
      <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
      {subtitle && <p className="mt-1 text-sm text-stone-600">{subtitle}</p>}
    </div>
    {actions && <div className="flex flex-wrap gap-2 no-print">{actions}</div>}
  </div>
);

const TONES = {
  paid: "bg-emerald-50 text-emerald-800 border-emerald-200", present: "bg-emerald-50 text-emerald-800 border-emerald-200",
  active: "bg-emerald-50 text-emerald-800 border-emerald-200", valid: "bg-emerald-50 text-emerald-800 border-emerald-200",
  pending: "bg-amber-50 text-amber-800 border-amber-200", late: "bg-amber-50 text-amber-800 border-amber-200",
  partially_paid: "bg-sky-50 text-sky-800 border-sky-200", half_day: "bg-sky-50 text-sky-800 border-sky-200",
  overdue: "bg-red-50 text-red-800 border-red-200", absent: "bg-red-50 text-red-800 border-red-200",
  inactive: "bg-red-50 text-red-800 border-red-200", reversed: "bg-stone-100 text-stone-500 border-stone-200 line-through",
  paid_leave: "bg-violet-50 text-violet-800 border-violet-200", former: "bg-stone-100 text-stone-700 border-stone-300",
};

export const StatusBadge = ({ status, label, testid }) => (
  <span data-testid={testid} className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${TONES[status] || "bg-stone-100 text-stone-700 border-stone-200"}`}>
    {label || LABELS[status] || status}
  </span>
);

export const StatCard = ({ label, value, money, hint, tone = "default", testid, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    disabled={!onClick}
    data-testid={testid}
    className={`card p-4 text-left transition-colors disabled:cursor-default ${onClick ? "hover:border-[#C6A15B]" : ""} ${tone === "dark" ? "!border-[#171717] !bg-[#171717] text-[#F7F5F0]" : ""}`}
  >
    <div className={`text-[11px] font-semibold uppercase tracking-wider ${tone === "dark" ? "text-[#C6A15B]" : "text-stone-500"}`}>{label}</div>
    <div className={`mt-2 font-num text-xl font-semibold sm:text-2xl ${tone === "danger" ? "text-[#8B1E2D]" : ""}`}>{money ? inr(value) : value}</div>
    {hint && <div className={`mt-1 text-xs ${tone === "dark" ? "text-stone-400" : "text-stone-500"}`}>{hint}</div>}
  </button>
);

export const Loader = ({ label = "Loading…" }) => (
  <div className="flex items-center justify-center gap-2 py-16 text-sm text-stone-500" data-testid="loader">
    <Loader2 className="h-4 w-4 animate-spin" /> {label}
  </div>
);

export const EmptyState = ({ title, hint, action, testid = "empty-state" }) => (
  <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-stone-300 bg-white/60 px-6 py-12 text-center" data-testid={testid}>
    <Inbox className="mb-3 h-8 w-8 text-stone-400" />
    <div className="font-semibold">{title}</div>
    {hint && <div className="mt-1 max-w-sm text-sm text-stone-500">{hint}</div>}
    {action && <div className="mt-4">{action}</div>}
  </div>
);

export const Field = ({ label, children, hint }) => (
  <label className="block">
    <span className="lbl">{label}</span>
    {children}
    {hint && <span className="mt-1 block text-xs text-stone-500">{hint}</span>}
  </label>
);

export const ErrorBox = ({ error }) =>
  error ? (
    <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" data-testid="form-error">
      {error}
    </div>
  ) : null;

export const Avatar = ({ name, photo, size = 40 }) =>
  photo ? (
    <img src={photo} alt={name} className="rounded-full object-cover" style={{ width: size, height: size }} />
  ) : (
    <div className="flex items-center justify-center rounded-full bg-[#171717] font-semibold text-[#C6A15B]" style={{ width: size, height: size, fontSize: size * 0.38 }}>
      {(name || "?").split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
    </div>
  );

export const Row = ({ k, v, strong, neg }) => (
  <div className={`flex items-center justify-between py-1.5 text-sm ${strong ? "border-t border-stone-200 pt-2.5 font-semibold" : ""}`}>
    <span className="text-stone-600">{k}</span>
    <span className={`font-num ${neg ? "text-[#8B1E2D]" : ""}`}>{v}</span>
  </div>
);
