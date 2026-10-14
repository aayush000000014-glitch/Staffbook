import axios from "axios";

export const TOKEN_KEY = "sb_token";
export const api = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api` });

api.interceptors.request.use((c) => {
  const t = localStorage.getItem(TOKEN_KEY);
  if (t) c.headers.Authorization = `Bearer ${t}`;
  return c;
});

api.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401 && !String(e.config?.url).startsWith("/auth/")) {
      localStorage.removeItem(TOKEN_KEY);
      window.location.href = "/login";
    }
    return Promise.reject(e);
  }
);

export function errMsg(e) {
  const d = e?.response?.data?.detail;
  if (d == null) return e?.message || "Something went wrong. Please try again.";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => (x && x.msg ? `${(x.loc || []).slice(-1)[0] || ""}: ${x.msg}` : JSON.stringify(x))).join(" ");
  return d.msg || String(d);
}

export const inr = (n) =>
  "₹" + Number(n || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export const fmtDate = (s) =>
  s ? new Date(`${s.slice(0, 10)}T00:00:00`).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";

export const todayISO = () => {
  const d = new Date(Date.now() + (330 + new Date().getTimezoneOffset()) * 60000);
  return d.toISOString().slice(0, 10);
};
export const monthISO = () => todayISO().slice(0, 7);
export const newRef = () => (window.crypto?.randomUUID ? window.crypto.randomUUID() : `${Date.now()}-${Math.random()}`);

export const LABELS = {
  fixed30: "Fixed 30 days", calendar: "Calendar days",
  fixed_date: "Fixed monthly date", cycle30: "30-day cycle", cycle40: "40-day cycle",
  absent: "Absent", half_day: "Half Day", paid_leave: "Paid Leave", late: "Late", present: "Present",
  cash: "Cash", upi: "UPI", bank: "Bank Transfer",
  pending: "Pending", overdue: "Overdue", partially_paid: "Partially Paid", paid: "Paid",
  monthly: "Monthly", yearly: "Yearly", active: "Active", former: "Former", inactive: "Inactive", valid: "Valid", reversed: "Reversed",
};

export const BUSINESS_TYPES = ["Shop / Retail", "Restaurant / Cafe", "Medical Store", "Kirana / Grocery", "Salon / Beauty", "Workshop / Garage", "Office / Services", "Other"];

export function readImage(file) {
  return new Promise((resolve, reject) => {
    if (!file) return resolve(null);
    if (!/^image\/(png|jpe?g|webp)$/.test(file.type)) return reject(new Error("Use a PNG, JPG or WEBP image"));
    if (file.size > 1024 * 1024) return reject(new Error("Image must be under 1MB"));
    const r = new FileReader();
    r.onload = () => resolve(r.result);
    r.onerror = () => reject(new Error("Could not read image"));
    r.readAsDataURL(file);
  });
}

export async function downloadCsv(path, params, filename) {
  const res = await api.get(path, { params, responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export const monthLabel = (m) => new Date(`${m}-01T00:00:00`).toLocaleDateString("en-IN", { month: "long", year: "numeric" });
export const shiftMonth = (m, k) => {
  const [y, mo] = m.split("-").map(Number);
  const d = new Date(y, mo - 1 + k, 1);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
};
export const daysIn = (m) => {
  const [y, mo] = m.split("-").map(Number);
  return new Date(y, mo, 0).getDate();
};
