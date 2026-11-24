import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { addDays, addMonths, format, parseISO } from "date-fns";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useSelectedStudent } from "./ParentPortal";
import { Button, Card, Input, PageHeader, QueryState, TableWrap, Tabs } from "../../components/ui";
import {
  AttendanceBadge, CalendarLegend, CompositionBar, MonthCalendar, SummaryTiles, WeeklyChart, YearlyChart,
} from "../../components/attendance/AttendanceVisuals";
import { parentApi } from "../../services/endpoints";
import { ABSENCE_REASONS } from "../../utils/attendance";
import { fmtDate, pct, todayISO } from "../../utils/format";

const VIEWS = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
  { value: "yearly", label: "Yearly" },
];

export function Stepper({ label, onPrev, onNext, children }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Button variant="secondary" size="sm" icon={ChevronLeft} onClick={onPrev} aria-label="Previous" />
      <span className="min-w-[150px] text-center font-semibold text-ink">{label}</span>
      <Button variant="secondary" size="sm" icon={ChevronRight} onClick={onNext} aria-label="Next" />
      {children}
    </div>
  );
}

const reasonText = (list) => (list?.length ? list.map((r) => ABSENCE_REASONS[r] || r).join(", ") : "—");

function DailyView({ studentId, date, setDate }) {
  const q = useQuery({ queryKey: ["parent", "daily", studentId, date], queryFn: () => parentApi.daily(studentId, date) });
  const day = q.data?.day;
  return (
    <Card title="Daily attendance – period-wise"
      action={<Stepper label={fmtDate(date, "EEE, dd MMM yyyy")} onPrev={() => setDate(format(addDays(parseISO(date), -1), "yyyy-MM-dd"))}
        onNext={() => setDate(format(addDays(parseISO(date), 1), "yyyy-MM-dd"))}>
        <Input type="date" value={date} onChange={(e) => e.target.value && setDate(e.target.value)} className="h-8 w-auto py-1 text-sm" aria-label="Pick a date" />
      </Stepper>}>
      <QueryState query={q}>
        {day && (
          <>
            <div className="mb-4 flex flex-wrap items-center gap-3">
              <AttendanceBadge status={day.category} />
              {day.title && <span className="text-sm text-muted">{day.title}</span>}
              {day.leave_status && <span className="text-sm text-muted">Leave request #{day.leave_request_id} – {day.leave_status}</span>}
            </div>
            {q.data.periods.length === 0 ? (
              <p className="rounded-xl bg-brand-50 px-4 py-6 text-center text-ink-soft">
                {day.day_type === "working" ? "No periods are scheduled for this day." : "No classes – this is a holiday, so it is not counted as an absence."}
              </p>
            ) : (
              <TableWrap>
                <table className="table-base">
                  <thead><tr><th>Period</th><th>Time</th><th>Subject</th><th>Status</th><th>Teacher</th><th>Reason / remarks</th></tr></thead>
                  <tbody>
                    {q.data.periods.map((p) => (
                      <tr key={p.period_number}>
                        <td className="num font-semibold">P{p.period_number}</td>
                        <td className="num whitespace-nowrap text-ink-soft">{p.start_time}–{p.end_time}</td>
                        <td>{p.subject}</td>
                        <td><AttendanceBadge status={p.status} /></td>
                        <td className="text-ink-soft">{p.teacher}{p.source === "substitute" && <span className="ml-1 text-xs text-muted">(substitute)</span>}</td>
                        <td className="text-ink-soft">{p.absence_reason ? ABSENCE_REASONS[p.absence_reason] : p.remarks || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            )}
          </>
        )}
      </QueryState>
    </Card>
  );
}

function DaysTable({ days, onPick }) {
  const rows = days.filter((d) => d.category !== "outside");
  return (
    <TableWrap>
      <table className="table-base">
        <thead><tr><th>Date</th><th>Status</th><th className="text-right">Present</th><th className="text-right">Absent</th><th className="text-right">Leave</th><th>Reason / note</th></tr></thead>
        <tbody>
          {rows.map((d) => (
            <tr key={d.date} className={onPick ? "cursor-pointer" : ""} onClick={() => onPick?.(d.date)}>
              <td className="whitespace-nowrap">{fmtDate(d.date, "EEE, dd MMM")}</td>
              <td><AttendanceBadge status={d.category} /></td>
              <td className="num text-right">{d.day_type === "working" ? d.present_periods : "—"}</td>
              <td className="num text-right">{d.day_type === "working" ? d.absent_periods + d.pending_leave_periods : "—"}</td>
              <td className="num text-right">{d.day_type === "working" ? d.leave_periods : "—"}</td>
              <td className="text-ink-soft">{d.day_type !== "working" ? d.title || "Holiday" : reasonText(d.absence_reasons)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

function WeeklyView({ studentId, date, setDate, openDay }) {
  const q = useQuery({ queryKey: ["parent", "weekly", studentId, date], queryFn: () => parentApi.weekly(studentId, date) });
  const w = q.data;
  return (
    <div className="space-y-6">
      <Card title="Weekly attendance" subtitle="Periods attended each day"
        action={w && <Stepper label={`${fmtDate(w.start_date, "dd MMM")} – ${fmtDate(w.end_date, "dd MMM yyyy")}`}
          onPrev={() => setDate(format(addDays(parseISO(date), -7), "yyyy-MM-dd"))} onNext={() => setDate(format(addDays(parseISO(date), 7), "yyyy-MM-dd"))} />}>
        <QueryState query={q}>
          {w && (
            <>
              <WeeklyChart days={w.days} />
              <p className="mt-4 text-sm text-ink-soft">This week: <b>{w.summary.present_days}</b> present, <b>{w.summary.partial_days}</b> partial,{" "}
                <b>{w.summary.absent_days}</b> absent, <b>{w.summary.approved_leave_days}</b> on approved leave · attendance {pct(w.summary.daily_percentage)}</p>
            </>
          )}
        </QueryState>
      </Card>
      {w && <Card title="Day-by-day summary" subtitle="Select a day to see period details"><DaysTable days={w.days} onPick={openDay} /></Card>}
    </div>
  );
}

function MonthlyView({ studentId, month, setMonth, openDay }) {
  const [y, mo] = month.split("-").map(Number);
  const q = useQuery({ queryKey: ["parent", "monthly", studentId, month], queryFn: () => parentApi.monthly(studentId, y, mo) });
  const data = q.data;
  const shift = (n) => setMonth(format(addMonths(new Date(y, mo - 1, 1), n), "yyyy-MM"));
  return (
    <div className="space-y-6">
      <Card title="Monthly attendance" action={<Stepper label={format(new Date(y, mo - 1, 1), "MMMM yyyy")} onPrev={() => shift(-1)} onNext={() => shift(1)} />}>
        <QueryState query={q}>
          {data && (
            <div className="grid gap-8 lg:grid-cols-[minmax(0,420px)_1fr]">
              <div><MonthCalendar days={data.days} onSelect={(d) => openDay(d.date)} /><div className="mt-4"><CalendarLegend /></div></div>
              <div className="space-y-5">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wide text-muted">Working days by status</p>
                  <div className="mt-2"><CompositionBar summary={data.summary} /></div>
                </div>
                <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
                  {[["Attendance", pct(data.summary.daily_percentage)], ["Period-wise", pct(data.summary.period_percentage)],
                    ["Working days", data.summary.total_working_days], ["School holidays", data.summary.school_holidays],
                    ["Festival holidays", data.summary.festival_holidays], ["Sundays / weekly", data.summary.weekly_holidays]].map(([k, v]) => (
                    <div key={k} className="rounded-xl border border-line p-3"><dt className="text-xs text-muted">{k}</dt><dd className="num text-lg font-semibold">{v}</dd></div>
                  ))}
                </dl>
              </div>
            </div>
          )}
        </QueryState>
      </Card>
      {data && <Card title="Working days this month"><DaysTable days={data.days.filter((d) => d.day_type === "working" && d.category !== "upcoming")} onPick={openDay} /></Card>}
    </div>
  );
}

function YearlyView({ studentId }) {
  const q = useQuery({ queryKey: ["parent", "yearly", studentId], queryFn: () => parentApi.yearly(studentId) });
  const data = q.data;
  return (
    <QueryState query={q}>
      {data && (
        <div className="space-y-6">
          <Card title={`Academic year ${data.academic_year}`} subtitle="Working days by status for each month"><YearlyChart months={data.months} /></Card>
          <Card title="Month-wise summary">
            <TableWrap>
              <table className="table-base">
                <thead><tr><th>Month</th><th className="text-right">Working days</th><th className="text-right">Present</th><th className="text-right">Partial</th><th className="text-right">Absent</th><th className="text-right">Approved leave</th><th className="text-right">Pending leave</th><th className="text-right">Attendance</th></tr></thead>
                <tbody>
                  {data.months.map((m) => (
                    <tr key={m.label}>
                      <td className="whitespace-nowrap font-medium">{m.label}</td>
                      <td className="num text-right">{m.total_working_days || "—"}</td>
                      <td className="num text-right">{m.present_days}</td>
                      <td className="num text-right">{m.partial_days}</td>
                      <td className="num text-right">{m.absent_days}</td>
                      <td className="num text-right">{m.approved_leave_days}</td>
                      <td className="num text-right">{m.pending_leave_days}</td>
                      <td className="num text-right font-semibold">{pct(m.daily_percentage)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          </Card>
        </div>
      )}
    </QueryState>
  );
}

export default function ParentAttendance() {
  const { student } = useSelectedStudent();
  const [view, setView] = useState("weekly");
  const [date, setDate] = useState(todayISO());
  const [month, setMonth] = useState(todayISO().slice(0, 7));
  const overview = useQuery({ queryKey: ["parent", "overview", student.id], queryFn: () => parentApi.overview(student.id) });
  const openDay = (d) => { setDate(d); setView("daily"); };
  const reasons = Object.entries(overview.data?.absence_reasons || {}).sort((a, b) => b[1] - a[1]);

  return (
    <>
      <PageHeader title="Attendance" description={`${student.full_name} · academic year ${overview.data?.academic_year ?? ""} to date. Holidays and Sundays are never counted as absent.`} />
      <QueryState query={overview}><SummaryTiles summary={overview.data} /></QueryState>
      {reasons.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Absence reasons this year:</span>
          {reasons.map(([k, v]) => <span key={k} className="rounded-full border border-line px-2.5 py-0.5 text-ink-soft">{ABSENCE_REASONS[k] || k} <b className="num">{v}</b></span>)}
        </div>
      )}
      <div className="my-6"><Tabs tabs={VIEWS} value={view} onChange={setView} /></div>
      {view === "daily" && <DailyView studentId={student.id} date={date} setDate={setDate} />}
      {view === "weekly" && <WeeklyView studentId={student.id} date={date} setDate={setDate} openDay={openDay} />}
      {view === "monthly" && <MonthlyView studentId={student.id} month={month} setMonth={setMonth} openDay={openDay} />}
      {view === "yearly" && <YearlyView studentId={student.id} />}
    </>
  );
}
