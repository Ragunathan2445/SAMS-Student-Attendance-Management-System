import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { format, subDays } from "date-fns";
import { GraduationCap } from "lucide-react";
import { useSelectedStudent } from "./ParentPortal";
import { Button, Card, EmptyState, Field, Input, PageHeader, QueryState, TableWrap, Tabs } from "../../components/ui";
import { AttendanceBadge } from "../../components/attendance/AttendanceVisuals";
import { LeaveList } from "./Leave";
import { LedgerTable, PaymentsTable } from "./Payments";
import { parentApi } from "../../services/endpoints";
import { ABSENCE_REASONS } from "../../utils/attendance";
import { fmtDate } from "../../utils/format";

const TABS = [
  { value: "attendance", label: "Attendance" },
  { value: "leave", label: "Leave requests" },
  { value: "payments", label: "Payments" },
  { value: "balance", label: "Fee balance" },
  { value: "academic", label: "Previous years" },
];

export default function History() {
  const { student } = useSelectedStudent();
  const [tab, setTab] = useState("attendance");
  const [range, setRange] = useState({ from: format(subDays(new Date(), 30), "yyyy-MM-dd"), to: format(new Date(), "yyyy-MM-dd") });
  const [draft, setDraft] = useState(range);
  const [onlyAbsences, setOnlyAbsences] = useState(false);
  const id = student.id;

  const attendance = useQuery({ queryKey: ["parent", "hist-att", id, range], queryFn: () => parentApi.attendanceHistory(id, range.from, range.to), enabled: tab === "attendance" });
  const leave = useQuery({ queryKey: ["parent", "hist-leave", id, range], queryFn: () => parentApi.leaveRequests({ student_id: id, from: range.from, to: range.to }), enabled: tab === "leave" });
  const payments = useQuery({ queryKey: ["parent", "hist-pay", id, range], queryFn: () => parentApi.payments(id, range.from, range.to), enabled: tab === "payments" });
  const balance = useQuery({ queryKey: ["parent", "hist-bal", id, range], queryFn: () => parentApi.balanceHistory(id, range.from, range.to), enabled: tab === "balance" });
  const academic = useQuery({ queryKey: ["parent", "academic", id], queryFn: () => parentApi.academicRecords(id), enabled: tab === "academic" });

  const days = (attendance.data?.days || []).filter((d) => !onlyAbsences || ["absent", "partial", "approved_leave", "pending_leave"].includes(d.category));
  const filterBar = tab !== "academic" && (
    <form className="flex flex-wrap items-end gap-3" onSubmit={(e) => { e.preventDefault(); setRange(draft); }}>
      <Field label="From"><Input type="date" value={draft.from} max={draft.to} onChange={(e) => setDraft({ ...draft, from: e.target.value })} className="w-auto" /></Field>
      <Field label="To"><Input type="date" value={draft.to} min={draft.from} onChange={(e) => setDraft({ ...draft, to: e.target.value })} className="w-auto" /></Field>
      <Button type="submit" variant="secondary">Apply</Button>
      {tab === "attendance" && (
        <label className="flex h-10 items-center gap-2 text-sm text-ink-soft">
          <input type="checkbox" checked={onlyAbsences} onChange={(e) => setOnlyAbsences(e.target.checked)} className="size-4 accent-[#6f4529]" /> Absences & leave only
        </label>
      )}
    </form>
  );

  return (
    <>
      <PageHeader title="History" description={`Records for ${student.full_name}, filtered by date.`} />
      <div className="mb-5"><Tabs tabs={TABS} value={tab} onChange={setTab} /></div>
      <Card title={TABS.find((t) => t.value === tab).label + " history"} action={filterBar}>
        {tab === "attendance" && (
          <QueryState query={attendance} empty={!days.length} emptyTitle="No records in this range">
            <TableWrap>
              <table className="table-base">
                <thead><tr><th>Date</th><th>Day</th><th>Status</th><th className="text-right">Periods present</th><th>Note</th></tr></thead>
                <tbody>
                  {days.map((d) => (
                    <tr key={d.date}>
                      <td className="whitespace-nowrap">{fmtDate(d.date)}</td>
                      <td>{d.weekday}</td>
                      <td><AttendanceBadge status={d.category} /></td>
                      <td className="num text-right">{d.day_type === "working" ? `${d.present_periods}/${d.scheduled_periods}` : "—"}</td>
                      <td className="text-ink-soft">{d.day_type !== "working" ? d.title : d.absence_reasons.map((r) => ABSENCE_REASONS[r]).join(", ") || (d.leave_status ? `Leave ${d.leave_status}` : "—")}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </TableWrap>
          </QueryState>
        )}
        {tab === "leave" && <QueryState query={leave}><LeaveList requests={leave.data?.requests || []} /></QueryState>}
        {tab === "payments" && <QueryState query={payments}><PaymentsTable payments={payments.data?.payments || []} /></QueryState>}
        {tab === "balance" && <QueryState query={balance}><LedgerTable entries={balance.data?.entries || []} /></QueryState>}
        {tab === "academic" && (
          <QueryState query={academic}>
            {academic.data?.records.length ? (
              <TableWrap>
                <table className="table-base">
                  <thead><tr><th>Academic year</th><th>Class</th><th className="text-right">Overall %</th><th>Grade</th><th className="text-right">Attendance</th><th>Result</th><th>Remarks</th></tr></thead>
                  <tbody>
                    {academic.data.records.map((r) => (
                      <tr key={r.academic_year}>
                        <td className="font-medium">{r.academic_year}</td>
                        <td>{r.class_name} – {r.section_name}</td>
                        <td className="num text-right">{r.percentage}%</td>
                        <td>{r.overall_grade}</td>
                        <td className="num text-right">{r.attendance_percentage}%</td>
                        <td>{r.result}</td>
                        <td className="text-ink-soft">{r.remarks}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            ) : <EmptyState icon={GraduationCap} title="No previous academic records">Records appear here after a student completes a year at the school.</EmptyState>}
          </QueryState>
        )}
      </Card>
    </>
  );
}
