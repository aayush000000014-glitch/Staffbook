import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { api, errMsg, todayISO, monthISO, monthLabel, shiftMonth, daysIn, LABELS } from "@/lib/api";
import { PageHeader, Loader, EmptyState, Avatar, ErrorBox } from "@/components/sb/Kit";
import { AttendanceDialog } from "@/components/sb/EntryDialogs";
import { useStaffOptions, StaffSelect } from "@/components/sb/staffOptions";

const CODES = [["present", "P"], ["absent", "A"], ["half_day", "H"], ["paid_leave", "PL"], ["late", "L"]];
const CELL = { absent: "bg-red-100 text-red-800", half_day: "bg-sky-100 text-sky-800", paid_leave: "bg-violet-100 text-violet-800", late: "bg-amber-100 text-amber-800" };

export const MonthNav = ({ month, setMonth }) => (
  <div className="flex items-center gap-1">
    <button className="btn-outline btn-sm" onClick={() => setMonth(shiftMonth(month, -1))} data-testid="month-prev"><ChevronLeft className="h-4 w-4" /></button>
    <div className="min-w-[140px] text-center text-sm font-semibold" data-testid="month-label">{monthLabel(month)}</div>
    <button className="btn-outline btn-sm" onClick={() => setMonth(shiftMonth(month, 1))} data-testid="month-next"><ChevronRight className="h-4 w-4" /></button>
  </div>
);

function QuickEntry({ staff }) {
  const [date, setDate] = useState(todayISO());
  const [map, setMap] = useState({});
  const [dlg, setDlg] = useState(null);
  const load = useCallback(() => {
    api.get("/attendance", { params: { month: date.slice(0, 7) } }).then((r) => setMap(Object.fromEntries(r.data.filter((a) => a.date === date).map((a) => [a.staff_id, a]))));
  }, [date]);
  useEffect(() => { load(); }, [load]);
  const set = async (s, code) => {
    const cur = map[s.id];
    try {
      if (code === "present") {
        if (cur) await api.delete(`/attendance/${s.id}/${date}`);
      } else if (code === "late") {
        setDlg({ staffId: s.id, existing: cur || null });
        return;
      } else {
        await api.put("/attendance", { staff_id: s.id, date, status: code, hours_late: 0 });
      }
      toast.success(`${s.name}: ${LABELS[code]}`);
      load();
    } catch (e) {
      toast.error(errMsg(e));
    }
  };
  const eligible = staff.filter((s) => s.joining_date <= date);
  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <input type="date" className="inp w-auto" value={date} onChange={(e) => setDate(e.target.value)} data-testid="quick-date-input" />
        <span className="text-xs text-stone-500">Tap to change. Everyone is Present unless marked.</span>
      </div>
      {eligible.length === 0 ? <EmptyState title="No staff employed on this date" /> : (
        <div className="card divide-y divide-stone-100" data-testid="quick-entry-list">
          {eligible.map((s) => {
            const cur = map[s.id]?.status || "present";
            return (
              <div key={s.id} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between" data-testid="quick-entry-row">
                <div className="flex items-center gap-2"><Avatar name={s.name} size={32} /><div><div className="text-sm font-semibold">{s.name}</div>{map[s.id]?.status === "late" && <div className="text-xs text-amber-700">{map[s.id].hours_late}h late</div>}</div></div>
                <div className="grid grid-cols-5 gap-1">
                  {CODES.map(([k, c]) => (
                    <button key={k} onClick={() => set(s, k)} title={LABELS[k]} data-testid={`quick-${k}-${s.id}`}
                      className={`h-9 min-w-[44px] rounded-md border text-xs font-bold ${cur === k ? (k === "present" ? "border-emerald-700 bg-emerald-700 text-white" : "border-[#8B1E2D] bg-[#8B1E2D] text-white") : "border-stone-300 bg-white text-stone-600"}`}>{c}</button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}
      <AttendanceDialog open={!!dlg} onOpenChange={(o) => !o && setDlg(null)} staffId={dlg?.staffId} date={date} existing={dlg?.existing} defaultStatus="late" onSaved={load} />
    </div>
  );
}

function MonthCalendar({ staff }) {
  const [month, setMonth] = useState(monthISO());
  const [sid, setSid] = useState("");
  const [rows, setRows] = useState(null);
  const [dlg, setDlg] = useState(null);
  useEffect(() => { if (!sid && staff[0]) setSid(staff[0].id); }, [staff, sid]);
  const load = useCallback(() => {
    if (sid) api.get("/attendance", { params: { month, staff_id: sid } }).then((r) => setRows(r.data));
  }, [month, sid]);
  useEffect(() => { load(); }, [load]);
  const s = staff.find((x) => x.id === sid);
  const map = Object.fromEntries((rows || []).map((a) => [a.date, a]));
  const n = daysIn(month);
  const offset = (new Date(`${month}-01T00:00:00`).getDay() + 6) % 7;
  const t = todayISO();
  return (
    <div>
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="sm:w-72"><StaffSelect value={sid} onChange={setSid} options={staff} testid="calendar-staff-select" /></div>
        <MonthNav month={month} setMonth={setMonth} />
      </div>
      {!s ? <EmptyState title="Select a staff member" /> : !rows ? <Loader /> : (
        <div className="card p-3 sm:p-5">
          <div className="grid grid-cols-7 gap-1 text-center text-[11px] font-semibold uppercase text-stone-500">{["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d}>{d}</div>)}</div>
          <div className="mt-1 grid grid-cols-7 gap-1" data-testid="attendance-calendar">
            {Array.from({ length: offset }).map((_, i) => <div key={`e${i}`} />)}
            {Array.from({ length: n }).map((_, i) => {
              const date = `${month}-${String(i + 1).padStart(2, "0")}`;
              const a = map[date];
              const employed = date >= s.joining_date && (!s.leaving_date || date <= s.leaving_date);
              return (
                <button key={date} disabled={!employed} onClick={() => setDlg({ date, existing: a || null })} data-testid={`cal-day-${date}`}
                  className={`flex aspect-square flex-col items-center justify-center rounded-md border text-xs ${!employed ? "border-transparent text-stone-300" : a ? `${CELL[a.status]} border-transparent font-semibold` : "border-stone-200 bg-white hover:border-[#C6A15B]"} ${date === t ? "ring-2 ring-[#C6A15B]" : ""}`}>
                  <span>{i + 1}</span>
                  {a && <span className="text-[9px]">{CODES.find((c) => c[0] === a.status)[1]}{a.status === "late" ? ` ${a.hours_late}h` : ""}</span>}
                </button>
              );
            })}
          </div>
          <div className="mt-4 flex flex-wrap gap-3 text-xs text-stone-600">{CODES.slice(1).map(([k, c]) => <span key={k} className="flex items-center gap-1"><span className={`rounded px-1.5 font-semibold ${CELL[k]}`}>{c}</span>{LABELS[k]}</span>)}<span>Blank = Present</span></div>
        </div>
      )}
      <AttendanceDialog open={!!dlg} onOpenChange={(o) => !o && setDlg(null)} staffId={sid} date={dlg?.date} existing={dlg?.existing} onSaved={load} />
    </div>
  );
}

export default function Attendance() {
  const staff = useStaffOptions();
  const [err] = useState("");
  return (
    <div data-testid="attendance-page">
      <PageHeader title="Attendance" subtitle="Exception-based: record only Absent, Half Day, Paid Leave or Late." />
      <ErrorBox error={err} />
      <Tabs defaultValue="quick">
        <TabsList className="mb-4">
          <TabsTrigger value="quick" data-testid="attendance-tab-quick">Quick entry</TabsTrigger>
          <TabsTrigger value="calendar" data-testid="attendance-tab-calendar">Monthly calendar</TabsTrigger>
        </TabsList>
        <TabsContent value="quick"><QuickEntry staff={staff} /></TabsContent>
        <TabsContent value="calendar"><MonthCalendar staff={staff} /></TabsContent>
      </Tabs>
    </div>
  );
}
