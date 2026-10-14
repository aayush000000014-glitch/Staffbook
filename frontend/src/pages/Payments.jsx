import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { api, errMsg, inr, fmtDate, monthISO, daysIn, todayISO, LABELS } from "@/lib/api";
import { PageHeader, Loader, EmptyState, StatusBadge } from "@/components/sb/Kit";
import { ObligationDialog } from "@/components/sb/ObligationDialog";
import { MonthNav } from "@/pages/Attendance";

const FILTERS = [["open", "All unpaid"], ["overdue", "Overdue"], ["pending", "Pending"], ["partially_paid", "Partially paid"], ["paid", "Paid"], ["", "All"]];
const DOT = { paid: "bg-emerald-600", overdue: "bg-red-600", partially_paid: "bg-sky-600", pending: "bg-amber-500" };

function ObList({ status, setStatus, onOpen, tick }) {
  const [rows, setRows] = useState(null);
  useEffect(() => {
    setRows(null);
    api.get("/obligations", { params: status ? { status } : {} }).then((r) => setRows(r.data)).catch((e) => toast.error(errMsg(e)));
  }, [status, tick]);
  return (
    <div>
      <div className="mb-3 flex gap-1.5 overflow-x-auto pb-1">
        {FILTERS.map(([k, l]) => (
          <button key={k} onClick={() => setStatus(k)} className={`whitespace-nowrap rounded-full border px-3 py-1.5 text-xs font-semibold ${status === k ? "border-[#171717] bg-[#171717] text-white" : "border-stone-300 bg-white"}`} data-testid={`pay-filter-${k || "all"}`}>{l}</button>
        ))}
      </div>
      {!rows ? <Loader /> : rows.length === 0 ? <EmptyState title="No payment records here" /> : (
        <div className="card divide-y divide-stone-100" data-testid="obligation-list">
          {rows.map((v) => (
            <button key={v.id} onClick={() => onOpen(v.id)} className="flex w-full items-center justify-between gap-3 p-4 text-left hover:bg-stone-50" data-testid="obligation-row">
              <div className="min-w-0">
                <div className="truncate font-semibold">{v.staff_name} {v.staff_status === "former" && <span className="text-xs font-normal text-stone-500">(former)</span>}</div>
                <div className="text-xs text-stone-500">Due {fmtDate(v.due_date)} · {fmtDate(v.period_start)} – {fmtDate(v.period_end)}{v.accruing && " · in progress"}</div>
              </div>
              <div className="text-right">
                <div className="font-num text-sm font-semibold">{inr(v.balance)}</div>
                <div className="mt-0.5 flex justify-end"><StatusBadge status={v.status} /></div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function PayCalendar({ onOpen, tick }) {
  const [month, setMonth] = useState(monthISO());
  const [rows, setRows] = useState(null);
  const [day, setDay] = useState(null);
  useEffect(() => {
    setRows(null);
    api.get("/calendar", { params: { month } }).then((r) => setRows(r.data));
  }, [month, tick]);
  const by = {};
  (rows || []).forEach((v) => { (by[v.due_date] = by[v.due_date] || []).push(v); });
  const n = daysIn(month);
  const offset = (new Date(`${month}-01T00:00:00`).getDay() + 6) % 7;
  const t = todayISO();
  const list = day ? by[day] || [] : rows || [];
  return (
    <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
      <div className="card p-3 sm:p-5">
        <div className="mb-3 flex justify-center sm:justify-end"><MonthNav month={month} setMonth={(m) => { setMonth(m); setDay(null); }} /></div>
        <div className="grid grid-cols-7 gap-1 text-center text-[11px] font-semibold uppercase text-stone-500">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d}>{d}</div>)}</div>
        <div className="mt-1 grid grid-cols-7 gap-1" data-testid="payment-calendar">
          {Array.from({ length: offset }).map((_, i) => <div key={`e${i}`} />)}
          {Array.from({ length: n }).map((_, i) => {
            const date = `${month}-${String(i + 1).padStart(2, "0")}`;
            const items = by[date] || [];
            return (
              <button key={date} onClick={() => setDay(day === date ? null : date)} data-testid={`pay-cal-${date}`}
                className={`flex aspect-square flex-col items-center justify-start rounded-md border p-1 text-xs ${day === date ? "border-[#8B1E2D] bg-[#8B1E2D]/5" : "border-stone-200 bg-white"} ${date === t ? "ring-2 ring-[#C6A15B]" : ""}`}>
                <span className={date === t ? "font-bold" : ""}>{i + 1}</span>
                <span className="mt-auto flex flex-wrap justify-center gap-0.5">{items.slice(0, 4).map((v) => <span key={v.id} className={`h-1.5 w-1.5 rounded-full ${DOT[v.status]}`} />)}</span>
              </button>
            );
          })}
        </div>
        <div className="mt-3 flex flex-wrap gap-3 text-xs text-stone-600">{Object.entries(DOT).map(([k, c]) => <span key={k} className="flex items-center gap-1"><span className={`h-2 w-2 rounded-full ${c}`} />{LABELS[k]}</span>)}</div>
      </div>
      <div>
        <div className="mb-2 text-sm font-semibold">{day ? `Due on ${fmtDate(day)}` : "All due this month"}</div>
        {!rows ? <Loader /> : list.length === 0 ? <EmptyState title="No payments due" /> : (
          <div className="card divide-y divide-stone-100" data-testid="calendar-day-list">
            {list.map((v) => (
              <button key={v.id} onClick={() => onOpen(v.id)} className="flex w-full items-center justify-between gap-2 p-3 text-left text-sm hover:bg-stone-50" data-testid="calendar-item">
                <div><div className="font-medium">{v.staff_name}</div><div className="text-xs text-stone-500">{fmtDate(v.due_date)}</div></div>
                <div className="flex items-center gap-2"><span className="font-num">{inr(v.status === "paid" ? v.paid : v.balance)}</span><StatusBadge status={v.status} /></div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function Transactions({ onOpen, tick }) {
  const [month, setMonth] = useState(monthISO());
  const [rows, setRows] = useState(null);
  useEffect(() => {
    setRows(null);
    api.get("/transactions", { params: { month } }).then((r) => setRows(r.data));
  }, [month, tick]);
  const total = (rows || []).filter((t) => t.status === "valid").reduce((a, t) => a + t.amount, 0);
  return (
    <div>
      <div className="mb-3 flex items-center justify-between"><MonthNav month={month} setMonth={setMonth} /><div className="text-sm">Total <span className="font-num font-semibold" data-testid="txn-month-total">{inr(total)}</span></div></div>
      {!rows ? <Loader /> : rows.length === 0 ? <EmptyState title="No transactions this month" /> : (
        <div className="card overflow-x-auto">
          <table className="tbl" data-testid="transactions-table">
            <thead><tr><th>Date</th><th>Staff</th><th>Period</th><th>Method</th><th>Amount</th><th>Status</th></tr></thead>
            <tbody>{rows.map((t) => (
              <tr key={t.id} className="cursor-pointer" onClick={() => onOpen(t.obligation_id)}>
                <td>{fmtDate(t.date)}</td><td className="font-medium">{t.staff_name}</td><td className="text-xs">{fmtDate(t.period_start)} – {fmtDate(t.period_end)}</td>
                <td>{LABELS[t.method]}</td><td className="font-num">{inr(t.amount)}</td><td><StatusBadge status={t.status} /></td>
              </tr>))}</tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function Payments() {
  const [sp, setSp] = useSearchParams();
  const [tab, setTab] = useState(sp.get("tab") || "list");
  const [status, setStatus] = useState(sp.get("status") ?? "open");
  const [oid, setOid] = useState(sp.get("open"));
  const [tick, setTick] = useState(0);
  const refresh = useCallback(() => setTick((x) => x + 1), []);
  const close = (o) => { if (!o) { setOid(null); if (sp.get("open")) { sp.delete("open"); setSp(sp, { replace: true }); } } };
  return (
    <div data-testid="payments-page">
      <PageHeader title="Payments" subtitle="Salary obligations, partial payments and the payment calendar." />
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="list" data-testid="payments-tab-list">Salary dues</TabsTrigger>
          <TabsTrigger value="calendar" data-testid="payments-tab-calendar">Calendar</TabsTrigger>
          <TabsTrigger value="transactions" data-testid="payments-tab-transactions">Transactions</TabsTrigger>
        </TabsList>
        <TabsContent value="list"><ObList status={status} setStatus={setStatus} onOpen={setOid} tick={tick} /></TabsContent>
        <TabsContent value="calendar"><PayCalendar onOpen={setOid} tick={tick} /></TabsContent>
        <TabsContent value="transactions"><Transactions onOpen={setOid} tick={tick} /></TabsContent>
      </Tabs>
      <ObligationDialog oid={oid} onOpenChange={close} onChanged={refresh} />
    </div>
  );
}
