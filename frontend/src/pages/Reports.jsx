import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Download, Printer } from "lucide-react";
import { api, errMsg, inr, monthISO, downloadCsv } from "@/lib/api";
import { PageHeader, Loader, EmptyState, ErrorBox, Field } from "@/components/sb/Kit";
import { StaffSelect } from "@/components/sb/staffOptions";

const KINDS = [
  ["salary_sheet", "Monthly salary sheet"], ["attendance", "Monthly attendance"], ["employee", "Employee salary history"],
  ["paid", "Paid payments"], ["pending", "Pending payments"], ["overdue", "Overdue payments"],
  ["advances", "Advances & deductions"], ["settlement", "Former staff settlement"],
];
const NEEDS_MONTH = ["salary_sheet", "attendance", "paid", "advances"];

const cell = (c, v) => (c.money ? inr(v) : v ?? "—");

export const ReportTable = ({ rep }) => (
  <div className="card overflow-x-auto print-area" data-testid="report-table">
    <div className="border-b border-stone-200 p-4">
      <div className="text-xs uppercase tracking-wider text-stone-500">{rep.business}</div>
      <div className="text-lg font-bold">{rep.title}</div>
      <div className="text-xs text-stone-500">{rep.subtitle} · Generated {rep.generated_on}</div>
    </div>
    {rep.rows.length === 0 ? <div className="p-6"><EmptyState title="No records for this report" /></div> : (
      <table className="tbl">
        <thead><tr>{rep.columns.map((c) => <th key={c.key} className={c.money ? "text-right" : ""}>{c.label}</th>)}</tr></thead>
        <tbody>{rep.rows.map((r, i) => <tr key={i}>{rep.columns.map((c) => <td key={c.key} className={c.money ? "text-right font-num" : ""}>{cell(c, r[c.key])}</td>)}</tr>)}</tbody>
        {Object.keys(rep.totals).length > 0 && (
          <tfoot><tr>{rep.columns.map((c, i) => <td key={c.key} className={c.money ? "text-right font-num" : ""} data-testid={c.money ? `report-total-${c.key}` : undefined}>{i === 0 ? "Total" : c.money ? inr(rep.totals[c.key]) : ""}</td>)}</tr></tfoot>
        )}
      </table>
    )}
  </div>
);

export default function Reports() {
  const [kind, setKind] = useState("salary_sheet");
  const [month, setMonth] = useState(monthISO());
  const [sid, setSid] = useState("");
  const [allStaff, setAllStaff] = useState([]);
  const [rep, setRep] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { api.get("/staff", { params: { status: "all" } }).then((r) => setAllStaff(r.data)); }, []);
  useEffect(() => {
    if (kind === "employee" && !sid) { setRep(null); return; }
    setRep(null);
    setErr("");
    api.get(`/reports/${kind}`, { params: { month, staff_id: sid || undefined } }).then((r) => setRep(r.data)).catch((e) => setErr(errMsg(e)));
  }, [kind, month, sid]);
  const csv = async () => {
    try { await downloadCsv(`/reports/${kind}/csv`, { month, staff_id: sid || undefined }, `staffbook_${kind}_${month}.csv`); } catch (e) { toast.error(errMsg(e)); }
  };
  return (
    <div data-testid="reports-page">
      <div className="no-print">
        <PageHeader title="Reports" subtitle="Built from saved records. Export CSV or print / save as PDF."
          actions={<>
            <button className="btn-outline" onClick={csv} disabled={!rep} data-testid="report-csv-btn"><Download className="h-4 w-4" /> CSV</button>
            <button className="btn-dark" onClick={() => window.print()} disabled={!rep} data-testid="report-print-btn"><Printer className="h-4 w-4" /> Print / PDF</button>
          </>} />
        <div className="mb-4 grid gap-3 sm:grid-cols-3">
          <Field label="Report">
            <select className="inp" value={kind} onChange={(e) => setKind(e.target.value)} data-testid="report-kind-select">{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
          </Field>
          {NEEDS_MONTH.includes(kind) && <Field label="Month"><input type="month" className="inp" value={month} onChange={(e) => setMonth(e.target.value)} data-testid="report-month-input" /></Field>}
          {kind === "employee" && <Field label="Staff"><StaffSelect value={sid} onChange={setSid} options={allStaff} testid="report-staff-select" /></Field>}
        </div>
      </div>
      <ErrorBox error={err} />
      {kind === "employee" && !sid ? <EmptyState title="Select a staff member" /> : !rep ? (!err && <Loader />) : <ReportTable rep={rep} />}
    </div>
  );
}
