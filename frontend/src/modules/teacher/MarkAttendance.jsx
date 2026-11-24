import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { format, subDays } from "date-fns";
import toast from "react-hot-toast";
import { CalendarOff, CheckCircle2, Pencil, UserRoundCheck } from "lucide-react";
import { Avatar, Badge, Button, Card, EmptyState, Field, Input, Modal, QueryState, Select, Textarea, cx } from "../../components/ui";
import AttendanceSheet from "../../components/attendance/AttendanceSheet";
import { AttendanceBadge } from "../../components/attendance/AttendanceVisuals";
import { teacherApi } from "../../services/endpoints";
import { errorMessage } from "../../services/api";
import { ABSENCE_REASONS, statusMeta } from "../../utils/attendance";
import { fmtDate, todayISO } from "../../utils/format";

function CorrectionModal({ row, onClose, onDone }) {
  const [status, setStatus] = useState(row?.status || "present");
  const [absence, setAbsence] = useState(row?.absence_reason || "");
  const [reason, setReason] = useState("");
  const m = useMutation({
    mutationFn: () => teacherApi.correctAttendance(row.attendance_id, { status, absence_reason: status === "absent" ? absence || null : null, reason }),
    onSuccess: (d) => { toast.success(d.message); onDone(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  if (!row) return null;
  return (
    <Modal open onClose={onClose} title={`Correct attendance – ${row.full_name}`}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button loading={m.isPending} disabled={reason.trim().length < 5} onClick={() => m.mutate()}>Save correction</Button></>}>
      <div className="space-y-4">
        <p className="text-sm text-ink-soft">Current: <AttendanceBadge status={row.status === "leave" ? "approved_leave" : row.status} />. Every correction is kept in the audit history.</p>
        <Field label="New status">
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="present">Present</option><option value="absent">Absent</option>
            <option value="leave" disabled={row.leave_status !== "approved"}>Approved leave</option>
          </Select>
        </Field>
        {status === "absent" && (
          <Field label="Absence reason"><Select value={absence} onChange={(e) => setAbsence(e.target.value)}>
            <option value="">Uninformed / not specified</option>
            {Object.entries(ABSENCE_REASONS).filter(([k]) => k !== "not_specified").map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select></Field>
        )}
        <Field label="Reason for correction" required hint="At least 5 characters"><Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="e.g. Student arrived late after the register was taken" /></Field>
      </div>
    </Modal>
  );
}

export default function MarkAttendance() {
  const qc = useQueryClient();
  const [date, setDate] = useState(todayISO());
  const [classId, setClassId] = useState("");
  const [sectionId, setSectionId] = useState("");
  const [periodId, setPeriodId] = useState("");
  const [correcting, setCorrecting] = useState(null);

  const slotsQ = useQuery({ queryKey: ["teacher", "slots", date], queryFn: () => teacherApi.slots(date) });
  const slots = slotsQ.data?.slots || [];
  const classes = useMemo(() => [...new Map(slots.map((s) => [s.class_name, s.class_name])).keys()], [slots]);
  const sections = slots.filter((s) => s.class_name === classId);
  const uniqSections = [...new Map(sections.map((s) => [s.section_id, s])).values()];
  const periods = slots.filter((s) => s.class_name === classId && String(s.section_id) === String(sectionId));
  const ready = sectionId && periodId;

  useEffect(() => { setClassId(""); setSectionId(""); setPeriodId(""); }, [date]);

  const pick = (s) => { setClassId(s.class_name); setSectionId(String(s.section_id)); setPeriodId(String(s.period_id)); };
  const sheetQ = useQuery({
    queryKey: ["teacher", "sheet", date, sectionId, periodId],
    queryFn: () => teacherApi.sheet({ date, section_id: sectionId, period_id: periodId }),
    enabled: Boolean(ready),
  });
  const submit = useMutation({
    mutationFn: (records) => teacherApi.submitAttendance({ date, section_id: Number(sectionId), period_id: Number(periodId), records }),
    onSuccess: (d) => {
      toast.success(`${d.message} ${d.counts.present} present, ${d.counts.absent} absent, ${d.counts.leave} on leave.`);
      qc.invalidateQueries({ queryKey: ["teacher"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const sheet = sheetQ.data;

  return (
    <div className="grid gap-6 xl:grid-cols-[360px_1fr]">
      <div className="space-y-6">
        <Card title="1 · Choose the period">
          <div className="space-y-4">
            <Field label="Attendance date" hint="Today or up to 7 days back">
              <Input type="date" value={date} max={todayISO()} min={format(subDays(new Date(), 7), "yyyy-MM-dd")} onChange={(e) => e.target.value && setDate(e.target.value)} />
            </Field>
            <Field label="Class">
              <Select value={classId} onChange={(e) => { setClassId(e.target.value); setSectionId(""); setPeriodId(""); }} disabled={!classes.length}>
                <option value="">Select class</option>{classes.map((c) => <option key={c}>{c}</option>)}
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Section">
                <Select value={sectionId} onChange={(e) => { setSectionId(e.target.value); setPeriodId(""); }} disabled={!classId}>
                  <option value="">Select</option>{uniqSections.map((s) => <option key={s.section_id} value={s.section_id}>{s.section_name}</option>)}
                </Select>
              </Field>
              <Field label="Period">
                <Select value={periodId} onChange={(e) => setPeriodId(e.target.value)} disabled={!sectionId}>
                  <option value="">Select</option>{periods.map((s) => <option key={s.period_id} value={s.period_id}>P{s.period_number} · {s.start_time}</option>)}
                </Select>
              </Field>
            </div>
          </div>
        </Card>
        <Card title={`Your timetable · ${fmtDate(date, "EEEE")}`} bodyClass="p-3">
          <QueryState query={slotsQ}>
            {!slotsQ.data?.is_working ? (
              <EmptyState icon={CalendarOff} title="Not a working day">{slotsQ.data?.title || "Holiday"} – no attendance is taken.</EmptyState>
            ) : !slots.length ? (
              <EmptyState title="No periods assigned to you on this day" />
            ) : (
              <ul className="space-y-1.5">
                {slots.map((s) => (
                  <li key={s.timetable_id}>
                    <button onClick={() => pick(s)}
                      className={cx("flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition hover:border-brand-400",
                        String(s.period_id) === periodId && String(s.section_id) === sectionId ? "border-brand-600 bg-brand-50" : "border-line")}>
                      <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-brand-700 text-sm font-semibold text-white">P{s.period_number}</span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium">{s.label}</span>
                        <span className="block text-xs text-muted">{s.subject} · {s.start_time}–{s.end_time}{s.substitute_teacher && ` · substitute: ${s.substitute_teacher}`}</span>
                      </span>
                      {s.is_marked ? <CheckCircle2 className="size-5 text-[#0e8a6a]" aria-label="Marked" /> : <Badge tone="muted">Open</Badge>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </QueryState>
        </Card>
      </div>

      <Card title="2 · Mark attendance" subtitle={sheet ? `${sheet.slot.label} · Period ${sheet.slot.period_number} (${sheet.slot.subject}) · ${fmtDate(date, "EEE dd MMM yyyy")}` : "Select a class, section and period"}>
        {!ready ? (
          <EmptyState icon={UserRoundCheck} title="Choose a period to load the class">Only classes and periods from your timetable can be selected.</EmptyState>
        ) : (
          <QueryState query={sheetQ}>
            {sheet && sheet.already_submitted ? (
              <div>
                <p className="mb-4 flex items-center gap-2 rounded-xl bg-[#e7f4ef] px-4 py-3 text-sm text-[#0a6a51]"><CheckCircle2 className="size-4" /> Attendance already submitted for this period. You can correct individual records with a reason.</p>
                <ul className="divide-y divide-line rounded-xl border border-line">
                  {sheet.students.map((s) => (
                    <li key={s.student_id} className="flex items-center gap-3 px-3 py-2.5">
                      <Avatar src={s.photo_url} name={s.full_name} size={40} rounded="rounded-xl" />
                      <div className="min-w-0 flex-1"><p className="truncate font-medium">{s.full_name}</p><p className="text-xs text-muted">Roll {s.roll_number}{s.absence_reason && ` · ${ABSENCE_REASONS[s.absence_reason]}`}</p></div>
                      {s.status ? <AttendanceBadge status={s.status === "leave" ? "approved_leave" : s.status} /> : <Badge tone="muted">Not in register</Badge>}
                      {s.attendance_id && <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setCorrecting(s)} aria-label="Correct" />}
                    </li>
                  ))}
                </ul>
              </div>
            ) : sheet ? (
              <>
                {sheet.pending_substitute_submission_id && (
                  <p className="mb-4 rounded-xl bg-[#f1ecf7] px-4 py-3 text-sm text-[#5f4590]">A substitute teacher has submitted temporary attendance for this period (awaiting approval under Substitute Approval).</p>
                )}
                <AttendanceSheet students={sheet.students} submitting={submit.isPending} onSubmit={(records) => submit.mutate(records)}
                  note={`Saved as official attendance with your teacher ID and the time of submission. ${statusMeta("pending_leave").label} requests are shown for information only.`} />
              </>
            ) : null}
          </QueryState>
        )}
      </Card>
      {correcting && <CorrectionModal row={correcting} onClose={() => setCorrecting(null)} onDone={() => { setCorrecting(null); sheetQ.refetch(); }} />}
    </div>
  );
}
