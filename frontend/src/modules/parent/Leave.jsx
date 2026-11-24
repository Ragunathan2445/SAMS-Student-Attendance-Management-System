import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { FileText, MessageSquareQuote, Paperclip, Send } from "lucide-react";
import { useSelectedStudent } from "./ParentPortal";
import { Button, Card, EmptyState, Field, Input, PageHeader, QueryState, Select, StatusPill, Tabs, Textarea } from "../../components/ui";
import { parentApi } from "../../services/endpoints";
import { errorMessage, safeDownload } from "../../services/api";
import { LEAVE_REASONS } from "../../utils/attendance";
import { fmtDate, fmtDateTime, todayISO } from "../../utils/format";

const MAX_DOC = 5 * 1024 * 1024;
const schema = z.object({
  student_id: z.coerce.number().positive("Choose a student"),
  start_date: z.string().min(1, "Choose the first day of leave"),
  end_date: z.string().min(1, "Choose the last day of leave"),
  reason: z.enum(Object.keys(LEAVE_REASONS), { errorMap: () => ({ message: "Choose a reason" }) }),
  description: z.string().max(1000, "Keep the description under 1000 characters").optional(),
  document: z.any().optional()
    .refine((f) => !f?.[0] || f[0].size <= MAX_DOC, "File must be 5 MB or smaller")
    .refine((f) => !f?.[0] || ["application/pdf", "image/jpeg", "image/png"].includes(f[0].type), "Upload a PDF, JPG or PNG"),
}).refine((v) => v.end_date >= v.start_date, { path: ["end_date"], message: "End date cannot be before the start date" });

function LeaveForm({ students, defaultStudent }) {
  const qc = useQueryClient();
  const { register, handleSubmit, reset, formState: { errors } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: { student_id: defaultStudent, start_date: todayISO(), end_date: todayISO(), reason: "fever", description: "" },
  });
  const mutation = useMutation({
    mutationFn: (values) => {
      const fd = new FormData();
      ["student_id", "start_date", "end_date", "reason", "description"].forEach((k) => fd.append(k, values[k] ?? ""));
      if (values.document?.[0]) fd.append("document", values.document[0]);
      return parentApi.createLeave(fd);
    },
    onSuccess: () => {
      toast.success("Leave request submitted. The class teacher will review it.");
      reset({ student_id: defaultStudent, start_date: todayISO(), end_date: todayISO(), reason: "fever", description: "" });
      qc.invalidateQueries({ queryKey: ["parent"] });
    },
    onError: (e) => toast.error(errorMessage(e)),
  });

  return (
    <Card title="Request leave" subtitle="Submitting a request does not change attendance until the class teacher approves it.">
      <form onSubmit={handleSubmit((v) => mutation.mutate(v))} className="space-y-4" noValidate>
        <Field label="Student" error={errors.student_id?.message} required>
          <Select {...register("student_id")}>
            {students.filter((s) => s.status === "active").map((s) => <option key={s.id} value={s.id}>{s.full_name} – {s.class_label}</option>)}
          </Select>
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="From" error={errors.start_date?.message} required><Input type="date" {...register("start_date")} /></Field>
          <Field label="To" error={errors.end_date?.message} required><Input type="date" {...register("end_date")} /></Field>
        </div>
        <Field label="Reason" error={errors.reason?.message} required>
          <Select {...register("reason")}>{Object.entries(LEAVE_REASONS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
        </Field>
        <Field label="Additional description" error={errors.description?.message}>
          <Textarea placeholder="Anything the teacher should know" {...register("description")} />
        </Field>
        <Field label="Supporting document (optional)" error={errors.document?.message} hint="Medical certificate or letter – PDF, JPG or PNG, up to 5 MB">
          <Input type="file" accept="application/pdf,image/jpeg,image/png" className="py-1.5 file:mr-3 file:rounded-md file:border-0 file:bg-brand-100 file:px-3 file:py-1 file:text-sm file:text-brand-800" {...register("document")} />
        </Field>
        <Button type="submit" icon={Send} loading={mutation.isPending} className="w-full sm:w-auto">Submit leave request</Button>
      </form>
    </Card>
  );
}

export function LeaveList({ requests }) {
  if (!requests.length) return <EmptyState icon={FileText} title="No leave requests">Submitted requests and the teacher's decision will appear here.</EmptyState>;
  return (
    <ul className="divide-y divide-line">
      {requests.map((r) => (
        <li key={r.id} className="py-4 first:pt-0 last:pb-0">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-semibold">{fmtDate(r.start_date)}{r.end_date !== r.start_date && ` – ${fmtDate(r.end_date)}`}
                <span className="ml-2 text-sm font-normal text-muted">{r.days} day(s) · {r.reason_label}</span></p>
              <p className="text-sm text-ink-soft">{r.student_name} · {r.class_label}</p>
            </div>
            <StatusPill status={r.status} />
          </div>
          {r.description && <p className="mt-2 text-sm text-ink-soft">{r.description}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted">
            <span>Submitted {fmtDateTime(r.submitted_at)}</span>
            {r.decided_at && <span>{r.status === "approved" ? "Approved" : "Rejected"} by {r.decided_by} on {fmtDate(r.decided_at)}</span>}
            {r.has_document && (
              <button className="inline-flex items-center gap-1 font-medium text-brand-700 hover:underline"
                onClick={() => safeDownload(`/parent/leave-requests/${r.id}/document`, r.document_name).catch((e) => toast.error(errorMessage(e)))}>
                <Paperclip className="size-3.5" />{r.document_name}
              </button>
            )}
          </div>
          {r.teacher_remarks && (
            <p className="mt-2 flex items-start gap-2 rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-900">
              <MessageSquareQuote className="mt-0.5 size-4 shrink-0 text-brand-500" /> {r.teacher_remarks}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

export default function LeaveInformation() {
  const { student, students } = useSelectedStudent();
  const [status, setStatus] = useState("");
  const q = useQuery({ queryKey: ["parent", "leave", student.id, status], queryFn: () => parentApi.leaveRequests({ student_id: student.id, status }) });
  const all = q.data?.requests || [];
  return (
    <>
      <PageHeader title="Leave Information" description="Request leave for your child and follow the class teacher's decision." />
      <div className="grid gap-6 xl:grid-cols-[420px_1fr]">
        <LeaveForm key={student.id} students={students} defaultStudent={student.id} />
        <Card title={`Leave requests – ${student.full_name}`}
          action={<Tabs value={status} onChange={setStatus} tabs={[{ value: "", label: "All" }, { value: "pending", label: "Pending" }, { value: "approved", label: "Approved" }, { value: "rejected", label: "Rejected" }]} />}>
          <QueryState query={q}><LeaveList requests={all} /></QueryState>
        </Card>
      </div>
    </>
  );
}
