import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { BookOpen, Briefcase, ClipboardCheck, Mail, Phone, School, UsersRound } from "lucide-react";
import { Avatar, Badge, Card, InfoRow, PageHeader, QueryState, StatTile, TableWrap } from "../../components/ui";
import { teacherApi } from "../../services/endpoints";
import { fmtDate } from "../../utils/format";

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];

export default function TeacherDetails() {
  const q = useQuery({ queryKey: ["teacher", "profile"], queryFn: teacherApi.profile });
  const p = q.data;
  const grid = {};
  p?.timetable.forEach((t) => { grid[`${t.day_of_week}-${t.period_number}`] = t; });
  const maxPeriod = Math.max(0, ...(p?.timetable.map((t) => t.period_number) || [0]));

  return (
    <>
      <PageHeader title="Teacher Details" description="Your profile, responsibilities and weekly timetable for the current academic year." />
      <QueryState query={q}>
        {p && (
          <div className="space-y-6">
            <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
              <div className="card p-6 text-center">
                <Avatar src={p.photo_url} name={p.full_name} size={112} rounded="rounded-2xl" className="mx-auto" />
                <h2 className="mt-4 text-2xl font-semibold">{p.full_name}</h2>
                <p className="text-sm text-muted">{p.designation}</p>
                <Badge className="mt-3">Teacher ID {p.employee_code}</Badge>
                <ul className="mt-5 space-y-2 text-left text-sm text-ink-soft">
                  <li className="flex items-center gap-2 break-all"><Mail className="size-4 shrink-0 text-brand-500" />{p.email}</li>
                  <li className="flex items-center gap-2"><Phone className="size-4 text-brand-500" />{p.mobile}</li>
                  <li className="flex items-center gap-2"><Briefcase className="size-4 text-brand-500" />Joined {fmtDate(p.date_of_joining)}</li>
                </ul>
              </div>
              <div className="space-y-6">
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
                  <StatTile label="Subjects" value={p.subjects.length || "—"} icon={BookOpen} accent="#6f4529" />
                  <StatTile label="Sections" value={p.sections.length} icon={School} accent="#a26f45" />
                  <StatTile label="Periods / week" value={p.weekly_periods} icon={ClipboardCheck} accent="#bc8d63" />
                  <StatTile label="Pending approvals" value={p.pending_approvals + p.pending_leave_requests} sub="Leave + substitute" icon={UsersRound} accent="var(--color-st-pending)" />
                </div>
                <Card title="Profile">
                  <dl className="divide-y divide-line">
                    <InfoRow label="Qualification" value={p.qualification} />
                    <InfoRow label="Assigned subjects" value={p.subjects.join(", ")} />
                    <InfoRow label="Assigned classes" value={p.classes.join(", ")} />
                    <InfoRow label="Assigned sections" value={<span className="flex flex-wrap gap-1.5">{p.sections.map((s) => <Badge key={s.id} tone={s.is_class_teacher ? "leave" : "neutral"}>{s.label}{s.is_class_teacher && " · class teacher"}</Badge>)}</span>} />
                    <InfoRow label="Responsibilities" value={p.responsibilities.length ? (
                      <ul className="space-y-1">{p.responsibilities.map((r, i) => <li key={i}><b>{r.label}</b>{r.section && ` – ${r.section}`}{r.description && <span className="font-normal text-muted"> · {r.description}</span>}</li>)}</ul>
                    ) : "Subject teacher"} />
                  </dl>
                </Card>
              </div>
            </div>
            {p.timetable.length > 0 && (
              <Card title="Weekly timetable" subtitle="Your first period changes from day to day – attendance always follows this timetable."
                action={<Link to="/teacher/attendance" className="text-sm font-medium text-brand-700 hover:underline">Mark attendance →</Link>}>
                <TableWrap>
                  <table className="table-base">
                    <thead><tr><th>Day</th>{Array.from({ length: maxPeriod }, (_, i) => <th key={i}>P{i + 1}</th>)}</tr></thead>
                    <tbody>
                      {DAYS.map((d, di) => (
                        <tr key={d}>
                          <td className="font-semibold">{d}</td>
                          {Array.from({ length: maxPeriod }, (_, pi) => {
                            const slot = grid[`${di + 1}-${pi + 1}`];
                            return <td key={pi} className="min-w-[96px]">{slot ? <span className="block rounded-lg bg-brand-50 px-2 py-1 text-xs"><b className="text-brand-800">{slot.label}</b><br /><span className="text-muted">{slot.subject}</span></span> : <span className="text-xs text-muted">—</span>}</td>;
                          })}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableWrap>
              </Card>
            )}
          </div>
        )}
      </QueryState>
    </>
  );
}
