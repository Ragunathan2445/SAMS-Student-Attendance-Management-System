import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Check, ClipboardList, Paperclip, X } from "lucide-react";
import { Avatar, Button, Card, EmptyState, Field, Modal, QueryState, StatusPill, Tabs, Textarea } from "../../components/ui";
import { teacherApi } from "../../services/endpoints";
import { errorMessage, safeDownload } from "../../services/api";
import { fmtDate, fmtDateTime } from "../../utils/format";

export default function LeaveApprovals() {
  const qc = useQueryClient();
  const [status, setStatus] = useState("pending");
  const [deciding, setDeciding] = useState(null); // {leave, action}
  const [remarks, setRemarks] = useState("");
  const q = useQuery({ queryKey: ["teacher", "leave", status], queryFn: () => teacherApi.leaveRequests(status) });
  const m = useMutation({
    mutationFn: () => teacherApi.decideLeave(deciding.leave.id, { action: deciding.action, remarks: remarks || null }),
    onSuccess: (d) => { toast.success(d.message); setDeciding(null); setRemarks(""); qc.invalidateQueries({ queryKey: ["teacher"] }); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  const list = q.data?.requests || [];

  return (
    <Card title="Leave requests" subtitle="Requests from parents of students in your class-teacher sections. Approval updates attendance to approved leave."
      action={<Tabs value={status} onChange={setStatus} tabs={[{ value: "pending", label: "Pending" }, { value: "approved", label: "Approved" }, { value: "rejected", label: "Rejected" }, { value: "", label: "All" }]} />}>
      <QueryState query={q}>
        {!list.length ? <EmptyState icon={ClipboardList} title="No leave requests here">Only class teachers receive leave requests for their sections.</EmptyState> : (
          <ul className="divide-y divide-line">
            {list.map((lv) => (
              <li key={lv.id} className="flex flex-wrap items-start gap-4 py-4 first:pt-0 last:pb-0">
                <Avatar src={lv.photo_url} name={lv.student_name} size={48} rounded="rounded-xl" />
                <div className="min-w-[220px] flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold">{lv.student_name}</p><span className="text-sm text-muted">{lv.roll_number} · {lv.class_label}</span><StatusPill status={lv.status} />
                  </div>
                  <p className="mt-1 text-sm"><b>{fmtDate(lv.start_date)}{lv.end_date !== lv.start_date && ` – ${fmtDate(lv.end_date)}`}</b> · {lv.days} day(s) · {lv.reason_label}</p>
                  {lv.description && <p className="mt-1 text-sm text-ink-soft">“{lv.description}”</p>}
                  <p className="mt-1 text-xs text-muted">From {lv.parent_name} · {fmtDateTime(lv.submitted_at)}</p>
                  {lv.teacher_remarks && <p className="mt-2 rounded-lg bg-brand-50 px-3 py-1.5 text-sm">Your remarks: {lv.teacher_remarks}</p>}
                  {lv.has_document && (
                    <button className="mt-2 inline-flex items-center gap-1 text-sm font-medium text-brand-700 hover:underline"
                      onClick={() => safeDownload(`/teacher/leave-requests/${lv.id}/document`, lv.document_name).catch((e) => toast.error(errorMessage(e)))}>
                      <Paperclip className="size-4" />{lv.document_name}</button>
                  )}
                </div>
                {lv.status === "pending" && (
                  <div className="flex gap-2">
                    <Button size="sm" variant="secondary" icon={X} onClick={() => setDeciding({ leave: lv, action: "rejected" })}>Reject</Button>
                    <Button size="sm" icon={Check} onClick={() => setDeciding({ leave: lv, action: "approved" })}>Approve</Button>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </QueryState>
      <Modal open={Boolean(deciding)} onClose={() => setDeciding(null)} title={deciding?.action === "approved" ? "Approve leave" : "Reject leave"}
        footer={<><Button variant="secondary" onClick={() => setDeciding(null)}>Cancel</Button>
          <Button variant={deciding?.action === "approved" ? "primary" : "danger"} loading={m.isPending}
            disabled={deciding?.action === "rejected" && remarks.trim().length < 3} onClick={() => m.mutate()}>
            {deciding?.action === "approved" ? "Approve" : "Reject"}</Button></>}>
        {deciding && (
          <div className="space-y-3">
            <p className="text-sm text-ink-soft">{deciding.leave.student_name} · {fmtDate(deciding.leave.start_date)} – {fmtDate(deciding.leave.end_date)}</p>
            {deciding.action === "approved" && <p className="rounded-lg bg-[#fbf1e2] px-3 py-2 text-sm text-[#8f5f14]">Absent periods already recorded in this range will be changed to approved leave (logged as corrections).</p>}
            <Field label={deciding.action === "rejected" ? "Reason for rejection" : "Remarks for parent (optional)"} required={deciding.action === "rejected"}>
              <Textarea value={remarks} onChange={(e) => setRemarks(e.target.value)} />
            </Field>
          </div>
        )}
      </Modal>
    </Card>
  );
}
