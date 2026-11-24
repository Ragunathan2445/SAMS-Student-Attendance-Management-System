import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { ArrowLeft, Check, ClipboardPen, History, Inbox, ShieldCheck, X } from "lucide-react";
import { Avatar, Badge, Button, Card, EmptyState, Field, Modal, PageHeader, QueryState, StatusPill, TableWrap, Tabs, Textarea } from "../../components/ui";
import AttendanceSheet from "../../components/attendance/AttendanceSheet";
import { AttendanceBadge } from "../../components/attendance/AttendanceVisuals";
import { teacherApi } from "../../services/endpoints";
import { errorMessage } from "../../services/api";
import { ABSENCE_REASONS } from "../../utils/attendance";
import { fmtDate, fmtDateTime } from "../../utils/format";

function TemporaryAttendance() {
  const qc = useQueryClient();
  const [active, setActive] = useState(null);
  const q = useQuery({ queryKey: ["teacher", "sub-assignments"], queryFn: teacherApi.subAssignments });
  const sheet = useQuery({ queryKey: ["teacher", "sub-sheet", active], queryFn: () => teacherApi.subSheet(active), enabled: Boolean(active) });
  const submit = useMutation({
    mutationFn: (records) => teacherApi.subSubmit(active, records),
    onSuccess: (d) => { toast.success(d.message); setActive(null); qc.invalidateQueries({ queryKey: ["teacher"] }); },
    onError: (e) => toast.error(errorMessage(e)),
  });

  if (active) {
    const a = sheet.data?.assignment;
    return (
      <Card title="Temporary attendance" subtitle={a ? `${a.label} · Period ${a.period_number} (${a.subject}) · ${fmtDate(a.date, "EEE dd MMM yyyy")} · covering for ${a.regular_teacher}` : null}
        action={<Button variant="secondary" size="sm" icon={ArrowLeft} onClick={() => setActive(null)}>Back to duties</Button>}>
        <QueryState query={sheet}>
          {sheet.data && (
            <>
              <p className="mb-4 rounded-xl bg-[#f1ecf7] px-4 py-3 text-sm text-[#5f4590]">
                This submission is <b>temporary</b>. It becomes official attendance only after {a.responsible_teacher} approves it.
              </p>
              <AttendanceSheet students={sheet.data.students} submitting={submit.isPending} submitLabel="Submit for approval"
                onSubmit={(records) => submit.mutate(records)} note="Your teacher ID, the responsible teacher and the submission time are recorded." />
            </>
          )}
        </QueryState>
      </Card>
    );
  }

  const list = q.data?.assignments || [];
  return (
    <Card title="My substitute duties" subtitle="Classes the school has assigned you to cover (last 2 weeks and next 2 weeks)">
      <QueryState query={q}>
        {!list.length ? <EmptyState icon={Inbox} title="No substitute duties assigned to you" /> : (
          <TableWrap>
            <table className="table-base">
              <thead><tr><th>Date</th><th>Class</th><th>Period</th><th>Regular teacher</th><th>Status</th><th /></tr></thead>
              <tbody>
                {list.map((a) => (
                  <tr key={a.assignment_id}>
                    <td className="whitespace-nowrap">{fmtDate(a.date, "EEE dd MMM")}</td>
                    <td><p className="font-medium">{a.label}</p><p className="text-xs text-muted">{a.subject}</p></td>
                    <td className="num whitespace-nowrap">P{a.period_number} · {a.start_time}</td>
                    <td><p>{a.regular_teacher}</p><p className="text-xs text-muted">{a.reason}</p></td>
                    <td>{a.submission_status ? <StatusPill status={a.submission_status} /> : a.official_attendance_exists ? <Badge tone="success">Marked by regular teacher</Badge> : <Badge tone="muted">Not submitted</Badge>}</td>
                    <td className="text-right">
                      {a.can_submit ? <Button size="sm" icon={ClipboardPen} onClick={() => setActive(a.assignment_id)}>{a.submission_status === "rejected" ? "Re-submit" : "Mark"}</Button>
                        : new Date(a.date) > new Date() ? <span className="text-xs text-muted">Upcoming</span> : null}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </TableWrap>
        )}
      </QueryState>
    </Card>
  );
}

function SubmissionModal({ id, onClose }) {
  const qc = useQueryClient();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const q = useQuery({ queryKey: ["teacher", "sub-detail", id], queryFn: () => teacherApi.subDetail(id), enabled: Boolean(id) });
  const done = (d) => { toast.success(d.message); qc.invalidateQueries({ queryKey: ["teacher"] }); onClose(); };
  const approve = useMutation({ mutationFn: () => teacherApi.subApprove(id), onSuccess: done, onError: (e) => toast.error(errorMessage(e)) });
  const reject = useMutation({ mutationFn: () => teacherApi.subReject(id, reason), onSuccess: done, onError: (e) => toast.error(errorMessage(e)) });
  const s = q.data;
  return (
    <Modal open={Boolean(id)} onClose={onClose} title={`Temporary attendance #${id}`} width="max-w-3xl"
      footer={s?.can_decide && (rejecting ? (
        <><Button variant="secondary" onClick={() => setRejecting(false)}>Back</Button>
          <Button variant="danger" icon={X} loading={reject.isPending} disabled={reason.trim().length < 5} onClick={() => reject.mutate()}>Confirm rejection</Button></>
      ) : (
        <><Button variant="secondary" icon={X} onClick={() => setRejecting(true)}>Reject</Button>
          <Button icon={Check} loading={approve.isPending} onClick={() => approve.mutate()}>Approve & finalise</Button></>
      ))}>
      <QueryState query={q}>
        {s && (
          <div className="space-y-4">
            <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[["Substitute", s.substitute_teacher_name], ["Class", s.label], ["Date", fmtDate(s.date)], ["Period", `P${s.period_number}`]].map(([k, v]) => (
                <div key={k} className="rounded-xl bg-brand-50 p-3"><dt className="text-xs text-muted">{k}</dt><dd className="font-semibold">{v}</dd></div>
              ))}
            </dl>
            <div className="flex flex-wrap items-center gap-2">
              <Badge tone="present">✓ Present {s.present_count}</Badge><Badge tone="absent">✕ Absent {s.absent_count}</Badge><Badge tone="leave">L Leave {s.leave_count}</Badge>
              <StatusPill status={s.status} /><span className="text-xs text-muted">Submitted {fmtDateTime(s.submitted_at)}</span>
            </div>
            {rejecting && <Field label="Reason for rejection" required><Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Explain what is wrong so it can be corrected" autoFocus /></Field>}
            <ul className="max-h-[40vh] divide-y divide-line overflow-y-auto rounded-xl border border-line">
              {s.items.map((i) => (
                <li key={i.student_id} className="flex items-center gap-3 px-3 py-2">
                  <Avatar src={i.photo_url} name={i.full_name} size={36} rounded="rounded-lg" />
                  <div className="min-w-0 flex-1"><p className="truncate text-sm font-medium">{i.full_name}</p><p className="text-xs text-muted">Roll {i.roll_number}{i.absence_reason && ` · ${ABSENCE_REASONS[i.absence_reason]}`}</p></div>
                  <AttendanceBadge status={i.status === "leave" ? "approved_leave" : i.status} />
                </li>
              ))}
            </ul>
            {s.rejection_reason && <p className="rounded-lg bg-[#fbebe8] px-3 py-2 text-sm text-[#7d2a19]">Rejected: {s.rejection_reason}</p>}
            {s.audit_trail.length > 0 && (
              <div>
                <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted"><ShieldCheck className="size-3.5" />Audit trail</p>
                <ul className="space-y-1 text-sm text-ink-soft">
                  {s.audit_trail.map((t, idx) => <li key={idx}>{fmtDateTime(t.acted_at)} – <b>{t.action}</b> by {t.acted_by}{t.records_finalized ? ` (${t.records_finalized} records finalised)` : ""}{t.reason && ` · “${t.reason}”`}</li>)}
                </ul>
              </div>
            )}
          </div>
        )}
      </QueryState>
    </Modal>
  );
}

function SubmissionList({ query, empty, onOpen, showSubstitute = true }) {
  const list = query.data?.submissions || [];
  return (
    <QueryState query={query}>
      {!list.length ? <EmptyState icon={Inbox} title={empty} /> : (
        <TableWrap>
          <table className="table-base">
            <thead><tr><th>Submitted</th>{showSubstitute ? <th>Substitute</th> : <th>Responsible teacher</th>}<th>Class</th><th>Date & period</th><th>Summary</th><th>Status</th><th /></tr></thead>
            <tbody>
              {list.map((s) => (
                <tr key={s.submission_id}>
                  <td className="whitespace-nowrap text-xs text-ink-soft">{fmtDateTime(s.submitted_at)}</td>
                  <td className="font-medium">{showSubstitute ? s.substitute_teacher_name : s.responsible_teacher_name}</td>
                  <td>{s.label}</td>
                  <td className="whitespace-nowrap">{fmtDate(s.date, "dd MMM")} · P{s.period_number}</td>
                  <td className="num whitespace-nowrap text-sm"><span className="text-[#0a6a51]">{s.present_count} P</span> · <span className="text-[#a3341f]">{s.absent_count} A</span> · <span className="text-[#8f5f14]">{s.leave_count} L</span></td>
                  <td><StatusPill status={s.status} />{s.decided_by && <p className="mt-0.5 text-xs text-muted">by {s.decided_by}</p>}</td>
                  <td className="text-right"><Button size="sm" variant={s.status === "pending" && showSubstitute ? "primary" : "secondary"} onClick={() => onOpen(s.submission_id)}>{s.status === "pending" && showSubstitute ? "Review" : "View"}</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      )}
    </QueryState>
  );
}

export default function SubstituteAttendance() {
  const { profile } = useOutletContext() || {};
  const [tab, setTab] = useState(profile?.pending_approvals ? "approvals" : "duties");
  const [status, setStatus] = useState("pending");
  const [open, setOpen] = useState(null);
  const approvals = useQuery({ queryKey: ["teacher", "sub-approvals", status], queryFn: () => teacherApi.subApprovals(status), enabled: tab === "approvals" });
  const mine = useQuery({ queryKey: ["teacher", "sub-mine"], queryFn: teacherApi.subMine, enabled: tab === "mine" });
  return (
    <>
      <PageHeader title="Substitute Attendance Approval" description="When a regular teacher is absent, the assigned substitute marks temporary attendance. The responsible teacher approves it before it becomes official." />
      <div className="mb-6">
        <Tabs value={tab} onChange={setTab} tabs={[
          { value: "duties", label: "Temporary attendance", icon: ClipboardPen },
          { value: "approvals", label: "Approvals for my classes", icon: ShieldCheck, count: profile?.pending_approvals },
          { value: "mine", label: "My submissions", icon: History },
        ]} />
      </div>
      {tab === "duties" && <TemporaryAttendance />}
      {tab === "approvals" && (
        <Card title="Submissions awaiting your decision" subtitle="Pending submissions are never counted as official attendance."
          action={<Tabs value={status} onChange={setStatus} tabs={[{ value: "pending", label: "Pending" }, { value: "approved", label: "Approved" }, { value: "rejected", label: "Rejected" }, { value: "", label: "All" }]} />}>
          <SubmissionList query={approvals} empty="No submissions here" onOpen={setOpen} />
        </Card>
      )}
      {tab === "mine" && <Card title="Temporary attendance I submitted"><SubmissionList query={mine} empty="You have not submitted any temporary attendance" onOpen={setOpen} showSubstitute={false} /></Card>}
      <SubmissionModal key={open ?? "none"} id={open} onClose={() => setOpen(null)} />
    </>
  );
}
