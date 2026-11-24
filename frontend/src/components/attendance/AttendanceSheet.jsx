import { useEffect, useMemo, useState } from "react";
import { Check, CheckCheck, Plane, X } from "lucide-react";
import { Avatar, Badge, Button, Select, cx } from "../ui";
import { ABSENCE_REASONS } from "../../utils/attendance";

const OPTIONS = [
  { value: "present", label: "Present", icon: Check, active: "bg-[#0e8a6a] text-white ring-[#0e8a6a]" },
  { value: "absent", label: "Absent", icon: X, active: "bg-[#c2412d] text-white ring-[#c2412d]" },
  { value: "leave", label: "Leave", icon: Plane, active: "bg-[#c98a2b] text-white ring-[#c98a2b]" },
];

/**
 * Roster for marking one period. `students` come from the backend sheet endpoint and already
 * include leave status: "Leave" can only be chosen for students with approved leave.
 */
export default function AttendanceSheet({ students, onSubmit, submitting, submitLabel = "Submit attendance", note }) {
  const initial = useMemo(
    () => Object.fromEntries(students.map((s) => [s.student_id, { status: s.suggested_status, absence_reason: "" }])),
    [students],
  );
  const [marks, setMarks] = useState(initial);
  useEffect(() => setMarks(initial), [initial]);

  const set = (id, patch) => setMarks((m) => ({ ...m, [id]: { ...m[id], ...patch } }));
  const counts = Object.values(marks).reduce((a, m) => ({ ...a, [m.status]: (a[m.status] || 0) + 1 }), {});

  const submit = () =>
    onSubmit(students.map((s) => {
      const m = marks[s.student_id];
      return { student_id: s.student_id, status: m.status, absence_reason: m.status === "absent" ? m.absence_reason || "uninformed" : null };
    }));

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2 text-sm">
          <Badge tone="present">✓ Present {counts.present || 0}</Badge>
          <Badge tone="absent">✕ Absent {counts.absent || 0}</Badge>
          <Badge tone="leave">L Leave {counts.leave || 0}</Badge>
          <Badge>Total {students.length}</Badge>
        </div>
        <Button size="sm" variant="subtle" icon={CheckCheck}
          onClick={() => setMarks(Object.fromEntries(students.map((s) => [s.student_id, { status: s.leave_status === "approved" ? "leave" : "present", absence_reason: "" }])))}>
          Mark all present
        </Button>
      </div>
      <ul className="divide-y divide-line rounded-xl border border-line">
        {students.map((s) => {
          const m = marks[s.student_id] || { status: "present" };
          return (
            <li key={s.student_id} className={cx("flex flex-wrap items-center gap-3 px-3 py-2.5 sm:flex-nowrap", m.status === "absent" && "bg-[#fdf6f4]")}>
              <Avatar src={s.photo_url} name={s.full_name} size={44} rounded="rounded-xl" />
              <div className="min-w-0 flex-1">
                <p className="truncate font-medium">{s.full_name}</p>
                <p className="text-xs text-muted">Roll {s.roll_number}
                  {s.leave_status === "approved" && <span className="ml-2 text-[#8f5f14]">· approved leave today</span>}
                  {s.leave_status === "pending" && <span className="ml-2 text-[#5f4590]">· leave request pending</span>}
                </p>
              </div>
              {m.status === "absent" && (
                <Select value={m.absence_reason} onChange={(e) => set(s.student_id, { absence_reason: e.target.value })} className="h-9 w-full py-1 text-sm sm:w-48" aria-label={`Absence reason for ${s.full_name}`}>
                  <option value="">Reason (optional)</option>
                  {Object.entries(ABSENCE_REASONS).filter(([k]) => k !== "not_specified").map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </Select>
              )}
              <div className="flex gap-1" role="radiogroup" aria-label={`Attendance for ${s.full_name}`}>
                {OPTIONS.map((o) => {
                  const disabled = o.value === "leave" && s.leave_status !== "approved";
                  const active = m.status === o.value;
                  return (
                    <button key={o.value} type="button" role="radio" aria-checked={active} disabled={disabled}
                      title={disabled ? "Leave can be marked only for an approved leave request" : o.label}
                      onClick={() => set(s.student_id, { status: o.value })}
                      className={cx("flex h-9 items-center gap-1 rounded-lg px-2.5 text-sm font-medium ring-1 ring-inset transition disabled:cursor-not-allowed disabled:opacity-35",
                        active ? o.active : "bg-white text-ink-soft ring-line hover:bg-brand-50")}>
                      <o.icon className="size-4" /><span className="hidden sm:inline">{o.label}</span>
                    </button>
                  );
                })}
              </div>
            </li>
          );
        })}
      </ul>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-muted">{note}</p>
        <Button onClick={submit} loading={submitting} disabled={!students.length}>{submitLabel}</Button>
      </div>
    </div>
  );
}
