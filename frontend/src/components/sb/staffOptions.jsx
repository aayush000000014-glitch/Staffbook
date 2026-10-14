import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export function useStaffOptions(enabled = true) {
  const [list, setList] = useState([]);
  useEffect(() => {
    if (enabled) {
      api.get("/staff", { params: { status: "active" } }).then((r) => setList(r.data)).catch(() => setList([]));
    }
  }, [enabled]);
  return list;
}

export const StaffSelect = ({ value, onChange, options, testid = "staff-select" }) => (
  <select className="inp" value={value} onChange={(e) => onChange(e.target.value)} data-testid={testid}>
    <option value="">Select staff…</option>
    {options.map((s) => (
      <option key={s.id} value={s.id}>{s.name}{s.designation ? ` · ${s.designation}` : ""}</option>
    ))}
  </select>
);
