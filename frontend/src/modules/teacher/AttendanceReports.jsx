import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format, startOfMonth } from "date-fns";
import toast from "react-hot-toast";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AlertTriangle, Download, Percent, TrendingDown, Users } from "lucide-react";
import { Avatar, Badge, Button, Card, EmptyState, Field, Input, Modal, QueryState, Select, StatTile, TableWrap } from "../../components/ui";
import { SummaryTiles, YearlyChart } from "../../components/attendance/AttendanceVisuals";
import { qs, teacherApi } from "../../services/endpoints";
import { errorMessage, safeDownload } from "../../services/api";
import { fmtDate, pct, todayISO } from "../../utils/format";

function DailyTrend({ daily }) {
  const data = daily.map((d) => ({ ...d, value: d.percentage === null ? null : Number(d.percentage), label: fmtDate(d.date, "dd MMM") }));
  return (
    <div className="h-56">
      <ResponsiveContainer>
        <LineChart data={data} margin={{ top: 8, right: 12, left: -16, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="#f0e9e1" />
          <XAxis dataKey="label" tickLine={false} axisLine={{ stroke: "#e2d7cb" }} minTickGap={24} />
          <YAxis domain={[50, 100]} tickLine={false} axisLine={false} width={44} unit="%" />
          <Tooltip cursor={{ stroke: "#bc8d63", strokeDasharray: "3 3" }}
            content={({ active, payload }) => active && payload?.length ? (
              <div className="rounded-xl border border-line bg-white px-3 py-2 text-xs shadow-lg">
                <p className="font-semibold">{fmtDate(payload[0].payload.date, "EEE dd MMM yyyy")}</p>
                <p className="num mt-1">Attendance <b>{pct(payload[0].payload.percentage)}</b></p>
                <p className="text-muted">{payload[0].payload.present} present · {payload[0].payload.absent} absent · {payload[0].payload.approved_leave} leave</p>
              </div>
            ) : null} />
          <Line type="monotone" dataKey="value" stroke="#6f4529" strokeWidth={2} dot={false} activeDot={{ r: 5, stroke: "#fff", strokeWidth: 2 }} isAnimationActive={false} connectNulls />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function StudentDrilldown({ studentId, onClose }) {
  const q = useQuery({ queryKey: ["teacher", "student-report", studentId], queryFn: () => teacherApi.studentReport(studentId), enabled: Boolean(studentId) });
  return (
    <Modal open={Boolean(studentId)} onClose={onClose} title="Student attendance report" width="max-w-4xl">
      <QueryState query={q}>
        {q.data && (
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <Avatar src={q.data.student.photo_url} name={q.data.student.full_name} size={52} rounded="rounded-xl" />
              <div><p className="text-lg font-semibold">{q.data.student.full_name}</p><p className="text-sm text-muted">{q.data.student.class_label} · Roll {q.data.student.roll_number}</p></div>
            </div>
            <SummaryTiles summary={q.data.overview} />
            <YearlyChart months={q.data.yearly.months} />
          </div>
        )}
      </QueryState>
    </Modal>
  );
}

const StudentRow = ({ r, onOpen, extra }) => (
  <tr className="cursor-pointer" onClick={() => onOpen(r.student_id)}>
    <td><span className="flex items-center gap-2.5"><Avatar src={r.photo_url} name={r.full_name} size={32} /><span><span className="block font-medium">{r.full_name}</span><span className="text-xs text-muted">{r.roll_number} · {r.class_label}</span></span></span></td>
    {extra}
  </tr>
);

export default function AttendanceReports() {
  const sectionsQ = useQuery({ queryKey: ["teacher", "sections"], queryFn: teacherApi.sections });
  const [filters, setFilters] = useState({ section_id: "", student_id: "", from: format(startOfMonth(new Date()), "yyyy-MM-dd"), to: todayISO() });
  const [applied, setApplied] = useState(filters);
  const [open, setOpen] = useState(null);
  const report = useQuery({ queryKey: ["teacher", "report", applied], queryFn: () => teacherApi.classReport(applied) });
  const monthly = useQuery({ queryKey: ["teacher", "monthly", applied.section_id], queryFn: () => teacherApi.monthly(applied.section_id) });
  const r = report.data;
  const roster = useQuery({ queryKey: ["teacher", "roster", filters.section_id], queryFn: () => teacherApi.directory({ section_id: filters.section_id }) });

  const exportXlsx = () => safeDownload(`/teacher/analytics/export${qs({ section_id: applied.section_id, from: applied.from, to: applied.to })}`, "attendance.xlsx")
    .then(() => toast.success("Excel report downloaded.")).catch((e) => toast.error(errorMessage(e)));

  return (
    <div className="space-y-6">
      <Card bodyClass="p-4">
        <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); setApplied(filters); }}>
          <Field label="Class & section" className="min-w-[180px]">
            <Select value={filters.section_id} onChange={(e) => setFilters({ ...filters, section_id: e.target.value, student_id: "" })}>
              <option value="">All my sections</option>
              {sectionsQ.data?.sections.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </Select>
          </Field>
          <Field label="Student" className="min-w-[200px]">
            <Select value={filters.student_id} onChange={(e) => setFilters({ ...filters, student_id: e.target.value })}>
              <option value="">All students</option>
              {roster.data?.students.map((s) => <option key={s.id} value={s.id}>{s.roll_number} · {s.full_name}</option>)}
            </Select>
          </Field>
          <Field label="From"><Input type="date" value={filters.from} max={filters.to} onChange={(e) => setFilters({ ...filters, from: e.target.value })} /></Field>
          <Field label="To"><Input type="date" value={filters.to} min={filters.from} max={todayISO()} onChange={(e) => setFilters({ ...filters, to: e.target.value })} /></Field>
          <Button type="submit">Apply filters</Button>
          <Button type="button" variant="secondary" icon={Download} onClick={exportXlsx}>Export Excel</Button>
        </form>
      </Card>

      <QueryState query={report}>
        {r && !r.overall ? <EmptyState title="No attendance data for these filters" /> : r && (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile label="Overall attendance" value={pct(r.overall.daily_percentage)} sub={`Period-wise ${pct(r.overall.period_percentage)}`} icon={Percent} accent="#6f4529" />
              <StatTile label="Students" value={r.overall.students} sub={`${r.overall.student_days_recorded} student-days recorded`} icon={Users} accent="#a26f45" />
              <StatTile label="Absent student-days" value={r.overall.absent_days} sub={`${r.overall.approved_leave_days} approved leave · ${r.overall.pending_leave_days} pending`} icon={TrendingDown} accent="var(--color-st-absent)" />
              <StatTile label="Repeated absences" value={r.repeated_absences.length} sub={`${r.criteria.streak}+ days in a row or ${r.criteria.total}+ absences`} icon={AlertTriangle} accent="var(--color-st-pending)" />
            </div>

            <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
              <Card title="Class attendance by day" subtitle={`${fmtDate(r.start_date)} – ${fmtDate(r.end_date)}`}>
                {r.daily.length ? <DailyTrend daily={r.daily} /> : <EmptyState title="No recorded days" />}
                {r.sections.length > 1 && (
                  <div className="mt-4 flex flex-wrap gap-2">{r.sections.map((s) => <Badge key={s.label}>{s.label}: {pct(s.percentage)}</Badge>)}</div>
                )}
              </Card>
              <Card title="Highest number of absences">
                {r.top_absentees.length ? (
                  <TableWrap><table className="table-base"><tbody>
                    {r.top_absentees.map((s) => <StudentRow key={s.student_id} r={s} onOpen={setOpen} extra={<><td className="num text-right font-semibold text-[#a3341f]">{s.absent_days} days</td><td className="num text-right">{pct(s.daily_percentage)}</td></>} />)}
                  </tbody></table></TableWrap>
                ) : <EmptyState title="No absences in this range" />}
              </Card>
            </div>

            <Card title="Students with repeated absences" subtitle="Consecutive working days absent (holidays do not break a streak) or frequent absences">
              {r.repeated_absences.length ? (
                <TableWrap><table className="table-base">
                  <thead><tr><th>Student</th><th className="text-right">Longest streak</th><th className="text-right">Absent days</th><th className="text-right">Attendance</th></tr></thead>
                  <tbody>{r.repeated_absences.map((s) => <StudentRow key={s.student_id} r={s} onOpen={setOpen} extra={<><td className="num text-right">{s.longest_absence_streak} day(s)</td><td className="num text-right">{s.absent_days}</td><td className="num text-right">{pct(s.daily_percentage)}</td></>} />)}</tbody>
                </table></TableWrap>
              ) : <EmptyState title="No repeated absences found" />}
            </Card>

            <Card title="Student-wise report" subtitle="Select a student for their full-year report">
              <TableWrap><table className="table-base">
                <thead><tr><th>Student</th><th className="text-right">Present</th><th className="text-right">Partial</th><th className="text-right">Absent</th><th className="text-right">Approved leave</th><th className="text-right">Pending</th><th className="text-right">Daily %</th><th className="text-right">Period %</th></tr></thead>
                <tbody>{r.students.map((s) => <StudentRow key={s.student_id} r={s} onOpen={setOpen} extra={<>
                  <td className="num text-right">{s.present_days}</td><td className="num text-right">{s.partial_days}</td><td className="num text-right">{s.absent_days}</td>
                  <td className="num text-right">{s.approved_leave_days}</td><td className="num text-right">{s.pending_leave_days}</td>
                  <td className="num text-right font-semibold">{pct(s.daily_percentage)}</td><td className="num text-right">{pct(s.period_percentage)}</td></>} />)}</tbody>
              </table></TableWrap>
            </Card>
          </>
        )}
      </QueryState>

      <Card title="Monthly attendance summary" subtitle="Academic year to date">
        <QueryState query={monthly} empty={!monthly.data?.months.length}>
          <TableWrap><table className="table-base">
            <thead><tr><th>Month</th><th className="text-right">Working days</th><th className="text-right">Present (student-days)</th><th className="text-right">Absent</th><th className="text-right">Approved leave</th><th className="text-right">Pending leave</th><th className="text-right">Attendance</th></tr></thead>
            <tbody>{monthly.data?.months.map((m) => (
              <tr key={m.label}><td className="font-medium">{m.label}</td><td className="num text-right">{m.working_days}</td><td className="num text-right">{m.present_days}</td>
                <td className="num text-right">{m.absent_days}</td><td className="num text-right">{m.approved_leave_days}</td><td className="num text-right">{m.pending_leave_days}</td>
                <td className="num text-right font-semibold">{pct(m.daily_percentage)}</td></tr>))}</tbody>
          </table></TableWrap>
        </QueryState>
      </Card>
      <StudentDrilldown studentId={open} onClose={() => setOpen(null)} />
    </div>
  );
}
