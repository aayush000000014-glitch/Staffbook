import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Search } from "lucide-react";
import { api, errMsg, inr, fmtDate, LABELS } from "@/lib/api";
import { PageHeader, Loader, EmptyState, StatusBadge, Avatar, ErrorBox } from "@/components/sb/Kit";
import { StaffFormDialog } from "@/components/sb/StaffFormDialog";

export default function Staff() {
  const [status, setStatus] = useState("active");
  const [q, setQ] = useState("");
  const [designation, setDesignation] = useState("");
  const [list, setList] = useState(null);
  const [err, setErr] = useState("");
  const [add, setAdd] = useState(false);
  const load = useCallback(() => {
    setErr("");
    api.get("/staff", { params: { status } }).then((r) => setList(r.data)).catch((e) => setErr(errMsg(e)));
  }, [status]);
  useEffect(() => { setList(null); load(); }, [load]);
  const designations = [...new Set((list || []).map((s) => s.designation).filter(Boolean))];
  const shown = (list || []).filter((s) =>
    (!q || `${s.name} ${s.designation} ${s.phone}`.toLowerCase().includes(q.toLowerCase())) && (!designation || s.designation === designation));
  return (
    <div data-testid="staff-page">
      <PageHeader title="Staff" subtitle={list && status === "active" ? `${list.length} of 100 active staff slots used` : "Your team"}
        actions={<button className="btn-primary" onClick={() => setAdd(true)} data-testid="add-staff-btn"><Plus className="h-4 w-4" /> Add staff</button>} />
      <div className="mb-4 flex flex-col gap-2 sm:flex-row">
        <div className="flex rounded-lg border border-stone-300 bg-white p-1">
          {["active", "former"].map((s) => (
            <button key={s} onClick={() => setStatus(s)} className={`flex-1 rounded-md px-4 py-1.5 text-sm font-semibold ${status === s ? "bg-[#171717] text-white" : "text-stone-600"}`} data-testid={`staff-tab-${s}`}>
              {s === "active" ? "Active" : "Former"}
            </button>
          ))}
        </div>
        <div className="relative flex-1">
          <Search className="absolute left-3 top-3 h-4 w-4 text-stone-400" />
          <input className="inp pl-9" placeholder="Search name, designation, phone" value={q} onChange={(e) => setQ(e.target.value)} data-testid="staff-search-input" />
        </div>
        <select className="inp sm:w-48" value={designation} onChange={(e) => setDesignation(e.target.value)} data-testid="staff-designation-filter">
          <option value="">All designations</option>
          {designations.map((d) => <option key={d}>{d}</option>)}
        </select>
      </div>
      <ErrorBox error={err} />
      {!list ? <Loader /> : shown.length === 0 ? (
        <EmptyState title={status === "active" ? "No active staff" : "No former staff"} hint={status === "active" ? "Add your first staff member to start tracking attendance and salary." : "Staff you mark as left appear here with full history."}
          action={status === "active" && <button className="btn-primary" onClick={() => setAdd(true)}>Add staff</button>} />
      ) : (
        <>
          <div className="grid gap-2 md:hidden" data-testid="staff-cards">
            {shown.map((s) => (
              <Link key={s.id} to={`/staff/${s.id}`} className="card flex items-center gap-3 p-3" data-testid="staff-card">
                <Avatar name={s.name} />
                <div className="min-w-0 flex-1">
                  <div className="truncate font-semibold">{s.name}</div>
                  <div className="truncate text-xs text-stone-500">{s.designation || "—"} · {inr(s.monthly_salary)}/mo</div>
                </div>
                <div className="text-right">
                  <div className="font-num text-sm font-semibold">{inr(s.outstanding)}</div>
                  <div className="text-[10px] uppercase text-stone-500">due</div>
                </div>
              </Link>
            ))}
          </div>
          <div className="card hidden overflow-x-auto md:block">
            <table className="tbl" data-testid="staff-table">
              <thead><tr><th>Name</th><th>Designation</th><th>Salary</th><th>Method</th><th>Schedule</th><th>Joined</th>{status === "former" && <th>Left</th>}<th>Outstanding</th><th>Advance</th><th>Status</th></tr></thead>
              <tbody>
                {shown.map((s) => (
                  <tr key={s.id} data-testid="staff-row">
                    <td><Link to={`/staff/${s.id}`} className="flex items-center gap-2 font-semibold hover:text-[#8B1E2D]"><Avatar name={s.name} size={30} />{s.name}</Link></td>
                    <td>{s.designation || "—"}</td>
                    <td className="font-num">{inr(s.monthly_salary)}</td>
                    <td>{LABELS[s.salary_method]}</td>
                    <td>{LABELS[s.schedule_type]}{s.schedule_type === "fixed_date" ? ` (${s.pay_day})` : ""}{s.cycle_paused && <span className="ml-1 text-xs text-amber-700">paused</span>}</td>
                    <td>{fmtDate(s.joining_date)}</td>
                    {status === "former" && <td>{fmtDate(s.leaving_date)}</td>}
                    <td className="font-num">{inr(s.outstanding)}</td>
                    <td className="font-num">{inr(s.advance_outstanding)}</td>
                    <td><StatusBadge status={s.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <StaffFormDialog open={add} onOpenChange={setAdd} onSaved={load} />
    </div>
  );
}
