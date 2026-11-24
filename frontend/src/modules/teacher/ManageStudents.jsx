import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { History, KeyRound, Pencil, RotateCcw, Search, UserMinus, UserPlus } from "lucide-react";
import { Avatar, Badge, Button, Card, EmptyState, Field, Input, Modal, PageHeader, QueryState, Select, StatusPill, TableWrap, Textarea } from "../../components/ui";
import { teacherApi } from "../../services/endpoints";
import { errorMessage } from "../../services/api";
import { fmtDate, fmtDateTime, titleCase } from "../../utils/format";

const NAME = /^[A-Za-z][A-Za-z .'-]{1,149}$/;
const MOBILE = /^(\+?91[\s-]?)?[6-9]\d{4}\s?\d{5}$/;
const CODE = /^[A-Za-z0-9\-/]{1,30}$/;
const totp = z.string().regex(/^\d{6}$/, "Enter the 6-digit code from Google Authenticator");
const BLOOD = ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"];

const base = {
  full_name: z.string().trim().regex(NAME, "Letters, spaces, '.', ''' and '-' only"),
  roll_number: z.string().trim().regex(CODE, "Letters, digits, '-' or '/' only"),
  date_of_birth: z.string().min(1, "Required"),
  gender: z.enum(["Male", "Female", "Other"]),
  blood_group: z.string().optional(),
  section_id: z.coerce.number().positive("Choose a section"),
  parent_name: z.string().trim().regex(NAME, "Enter the parent's name"),
  parent_mobile: z.string().trim().regex(MOBILE, "Enter a valid 10-digit mobile number"),
  parent_email: z.string().trim().email("Enter a valid e-mail"),
  address: z.string().trim().min(5, "Enter the residential address"),
  contact_number: z.string().trim().refine((v) => !v || MOBILE.test(v), "Enter a valid mobile number").optional(),
  uses_school_bus: z.boolean().optional(),
  reason: z.string().trim().min(5, "Give a reason (min. 5 characters)"),
  totp_code: totp,
};
const createSchema = z.object({ ...base, admission_number: z.string().trim().regex(CODE, "Letters, digits, '-' or '/' only"), photo: z.any().refine((f) => f?.[0], "A photograph is required") });
const editSchema = z.object({ ...base, photo: z.any().optional() });

function photoCheck(file) {
  if (!file) return null;
  if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) return "Photo must be JPG, PNG or WEBP";
  if (file.size > 2 * 1024 * 1024) return "Photo must be 2 MB or smaller";
  return null;
}

function StudentForm({ student, sections, onClose }) {
  const qc = useQueryClient();
  const editing = Boolean(student);
  const defaults = editing
    ? { ...student, blood_group: student.blood_group || "", contact_number: student.contact_number || "", reason: "", totp_code: "" }
    : { gender: "Female", section_id: sections[0]?.id, uses_school_bus: false, reason: "New admission", totp_code: "", blood_group: "", contact_number: "" };
  const { register, handleSubmit, setError, formState: { errors } } = useForm({ resolver: zodResolver(editing ? editSchema : createSchema), defaultValues: defaults });

  const m = useMutation({
    mutationFn: (v) => {
      const { photo, ...rest } = v;
      const payload = { ...rest, blood_group: rest.blood_group || null, contact_number: rest.contact_number || null };
      if (editing) delete payload.admission_number;
      const fd = new FormData();
      fd.append("payload", JSON.stringify(payload));
      if (photo?.[0]) fd.append("photo", photo[0]);
      return editing ? teacherApi.updateStudent(student.id, fd) : teacherApi.createStudent(fd);
    },
    onSuccess: (d) => {
      toast.success(editing ? `${d.full_name}'s details were updated.` : `${d.full_name} was added. Fees were assigned from the school's fee structure.`);
      qc.invalidateQueries({ queryKey: ["teacher"] });
      onClose();
    },
    onError: (e) => {
      const msg = errorMessage(e);
      if (e.response?.data?.code?.startsWith("totp")) setError("totp_code", { message: msg });
      toast.error(msg);
    },
  });

  const submit = (v) => {
    const err = photoCheck(v.photo?.[0]);
    if (err) return setError("photo", { message: err });
    m.mutate(v);
  };

  return (
    <Modal open onClose={onClose} width="max-w-3xl" title={editing ? `Update ${student.full_name}` : "Add a new student"}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button><Button form="student-form" type="submit" loading={m.isPending}>{editing ? "Save changes" : "Add student"}</Button></>}>
      <form id="student-form" onSubmit={handleSubmit(submit)} className="space-y-5" noValidate>
        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="mb-2 text-sm font-semibold uppercase tracking-wide text-brand-700">Student</legend>
          <Field label="Full name" error={errors.full_name?.message} required><Input {...register("full_name")} /></Field>
          <Field label="Roll number" error={errors.roll_number?.message} required><Input className="uppercase" placeholder="e.g. 6A11" {...register("roll_number")} /></Field>
          {!editing && <Field label="Admission number" error={errors.admission_number?.message} required><Input className="uppercase" placeholder="e.g. SVM-2026-1100" {...register("admission_number")} /></Field>}
          <Field label="Date of birth" error={errors.date_of_birth?.message} required><Input type="date" {...register("date_of_birth")} /></Field>
          <Field label="Gender" error={errors.gender?.message} required><Select {...register("gender")}><option>Female</option><option>Male</option><option>Other</option></Select></Field>
          <Field label="Blood group"><Select {...register("blood_group")}><option value="">Not known</option>{BLOOD.map((b) => <option key={b}>{b}</option>)}</Select></Field>
          <Field label="Class & section" error={errors.section_id?.message} required hint="Only your class-teacher sections">
            <Select {...register("section_id")}>{sections.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</Select>
          </Field>
          <Field label="Student contact (optional)" error={errors.contact_number?.message}><Input inputMode="tel" {...register("contact_number")} /></Field>
          <Field label={editing ? "Replace photograph (optional)" : "Photograph"} error={errors.photo?.message} required={!editing} hint="JPG, PNG or WEBP, up to 2 MB">
            <Input type="file" accept="image/jpeg,image/png,image/webp" className="py-1.5 file:mr-3 file:rounded-md file:border-0 file:bg-brand-100 file:px-3 file:py-1 file:text-sm file:text-brand-800" {...register("photo")} />
          </Field>
          <label className="flex items-center gap-2 self-end pb-2 text-sm text-ink-soft"><input type="checkbox" className="size-4 accent-[#6f4529]" {...register("uses_school_bus")} /> Uses the school bus</label>
        </fieldset>
        <fieldset className="grid gap-4 sm:grid-cols-2">
          <legend className="mb-2 text-sm font-semibold uppercase tracking-wide text-brand-700">Parent / guardian</legend>
          <Field label="Parent name" error={errors.parent_name?.message} required><Input {...register("parent_name")} /></Field>
          <Field label="Parent mobile" error={errors.parent_mobile?.message} required hint="Used for parent portal login"><Input inputMode="tel" {...register("parent_mobile")} /></Field>
          <Field label="Parent e-mail" error={errors.parent_email?.message} required><Input type="email" {...register("parent_email")} /></Field>
          <Field label="Residential address" error={errors.address?.message} required className="sm:col-span-2"><Textarea className="min-h-[64px]" {...register("address")} /></Field>
        </fieldset>
        <fieldset className="grid gap-4 rounded-xl border border-brand-200 bg-brand-50 p-4 sm:grid-cols-2">
          <Field label="Reason for this change" error={errors.reason?.message} required><Input {...register("reason")} placeholder={editing ? "e.g. Parent updated phone number" : "New admission"} /></Field>
          <Field label="Google Authenticator code" error={errors.totp_code?.message} required hint="Required for every student record change">
            <Input inputMode="numeric" maxLength={6} autoComplete="one-time-code" className="num font-mono tracking-[0.3em]" {...register("totp_code")} />
          </Field>
        </fieldset>
      </form>
    </Modal>
  );
}

function StatusModal({ student, onClose }) {
  const qc = useQueryClient();
  const deactivating = student.status === "active";
  const [reason, setReason] = useState("");
  const [code, setCode] = useState("");
  const [confirm, setConfirm] = useState(false);
  const m = useMutation({
    mutationFn: () => (deactivating ? teacherApi.deactivate : teacherApi.reactivate)(student.id, { reason, totp_code: code, confirm }),
    onSuccess: (d) => { toast.success(`${d.full_name} is now ${d.status}.`); qc.invalidateQueries({ queryKey: ["teacher"] }); onClose(); },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <Modal open onClose={onClose} title={deactivating ? `Remove (deactivate) ${student.full_name}` : `Reactivate ${student.full_name}`}
      footer={<><Button variant="secondary" onClick={onClose}>Cancel</Button>
        <Button variant={deactivating ? "danger" : "primary"} loading={m.isPending} disabled={!confirm || reason.trim().length < 5 || code.length !== 6} onClick={() => m.mutate()}>
          {deactivating ? "Deactivate student" : "Reactivate student"}</Button></>}>
      <div className="space-y-4">
        <div className="flex items-center gap-3 rounded-xl border border-line p-3">
          <Avatar src={student.photo_url} name={student.full_name} size={44} rounded="rounded-xl" />
          <div><p className="font-semibold">{student.full_name}</p><p className="text-sm text-muted">Roll {student.roll_number} · {student.admission_number} · {student.class_label}</p></div>
        </div>
        {deactivating && <p className="rounded-lg bg-[#fbf1e2] px-3 py-2 text-sm text-[#8f5f14]">The student is not deleted. Attendance, fee and academic history are kept; the student simply stops appearing in class lists.</p>}
        <Field label="Reason" required><Textarea value={reason} onChange={(e) => setReason(e.target.value)} placeholder={deactivating ? "e.g. Transfer certificate issued – relocating to Bengaluru" : "e.g. Re-admitted"} /></Field>
        <Field label="Google Authenticator code" required><Input inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} className="num font-mono tracking-[0.3em]" /></Field>
        <label className="flex items-start gap-2 text-sm"><input type="checkbox" checked={confirm} onChange={(e) => setConfirm(e.target.checked)} className="mt-0.5 size-4 accent-[#6f4529]" />
          I confirm I want to {deactivating ? "deactivate" : "reactivate"} this student record.</label>
      </div>
    </Modal>
  );
}

function HistoryModal({ student, onClose }) {
  const q = useQuery({ queryKey: ["teacher", "student-history", student.id], queryFn: () => teacherApi.studentHistory(student.id) });
  return (
    <Modal open onClose={onClose} title={`Change history – ${student.full_name}`} width="max-w-2xl">
      <QueryState query={q} empty={!q.data?.history.length} emptyTitle="No recorded changes">
        <ol className="space-y-3">
          {q.data?.history.map((h) => (
            <li key={h.id} className="rounded-xl border border-line p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <Badge tone={h.action === "deactivate" ? "danger" : h.action === "create" ? "success" : "neutral"}>{titleCase(h.action)}</Badge>
                <span className="text-xs text-muted">{fmtDateTime(h.performed_at)} · {h.performed_by} {h.totp_verified && "· TOTP verified"}</span>
              </div>
              <p className="mt-2 text-sm">Reason: {h.reason}</p>
              {h.action === "update" && (
                <ul className="mt-2 space-y-0.5 text-xs text-ink-soft">
                  {Object.entries(h.changes).map(([k, v]) => <li key={k}><b>{titleCase(k)}</b>: {String(v.old ?? "—")} → {String(v.new ?? "—")}</li>)}
                </ul>
              )}
            </li>
          ))}
        </ol>
      </QueryState>
    </Modal>
  );
}

export default function ManageStudents() {
  const [section, setSection] = useState("");
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const [inactive, setInactive] = useState(false);
  const [modal, setModal] = useState(null); // {type, student}
  const sectionsQ = useQuery({ queryKey: ["teacher", "sections"], queryFn: teacherApi.sections });
  const ctSections = sectionsQ.data?.class_teacher_sections || [];
  const list = useQuery({ queryKey: ["teacher", "manage", section, term, inactive], queryFn: () => teacherApi.manageList({ section_id: section, q: term, include_inactive: inactive }) });
  const students = list.data?.students || [];
  const hasAccess = useMemo(() => ctSections.length > 0, [ctSections]);

  return (
    <>
      <PageHeader title="Add & Remove Student Details" description="Class teachers can add, update and deactivate students in their own sections. Every change needs your authenticator code and is audited."
        actions={hasAccess && <Button icon={UserPlus} onClick={() => setModal({ type: "add" })}>Add student</Button>} />
      {sectionsQ.isSuccess && !hasAccess ? (
        <Card><EmptyState icon={KeyRound} title="Available to class teachers only">You are not a class teacher this year, so you cannot change student records. Contact the school office for corrections.</EmptyState></Card>
      ) : (
        <Card bodyClass="p-0">
          <form className="flex flex-wrap items-end gap-3 border-b border-line p-4" onSubmit={(e) => { e.preventDefault(); setTerm(search); }}>
            <Field label="Section" className="min-w-[160px]">
              <Select value={section} onChange={(e) => setSection(e.target.value)}><option value="">All my sections</option>{ctSections.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</Select>
            </Field>
            <Field label="Search" className="min-w-[220px] flex-1"><Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Name or roll number" /></Field>
            <Button type="submit" variant="secondary" icon={Search}>Search</Button>
            <label className="flex h-10 items-center gap-2 text-sm text-ink-soft"><input type="checkbox" checked={inactive} onChange={(e) => setInactive(e.target.checked)} className="size-4 accent-[#6f4529]" /> Show inactive</label>
          </form>
          <div className="p-5">
            <QueryState query={list}>
              {!students.length ? <EmptyState title="No students match" /> : (
                <TableWrap>
                  <table className="table-base">
                    <thead><tr><th>Student</th><th>Admission no.</th><th>Date of birth</th><th>Parent</th><th>Status</th><th className="text-right">Actions</th></tr></thead>
                    <tbody>
                      {students.map((s) => (
                        <tr key={s.id}>
                          <td><span className="flex items-center gap-2.5"><Avatar src={s.photo_url} name={s.full_name} size={36} rounded="rounded-lg" /><span><span className="block font-medium">{s.full_name}</span><span className="text-xs text-muted">{s.roll_number} · {s.class_label}</span></span></span></td>
                          <td className="num text-sm">{s.admission_number}</td>
                          <td className="whitespace-nowrap">{fmtDate(s.date_of_birth)}</td>
                          <td><p>{s.parent_name}</p><p className="text-xs text-muted">{s.parent_mobile}</p></td>
                          <td><StatusPill status={s.status} />{s.deactivation_reason && <p className="mt-0.5 max-w-[180px] truncate text-xs text-muted" title={s.deactivation_reason}>{s.deactivation_reason}</p>}</td>
                          <td>
                            <div className="flex justify-end gap-1">
                              {s.status === "active" && <Button size="sm" variant="ghost" icon={Pencil} onClick={() => setModal({ type: "edit", student: s })}>Edit</Button>}
                              <Button size="sm" variant="ghost" icon={History} onClick={() => setModal({ type: "history", student: s })} aria-label="History" />
                              {s.status === "active"
                                ? <Button size="sm" variant="ghost" icon={UserMinus} className="text-[#a3341f]" onClick={() => setModal({ type: "status", student: s })}>Remove</Button>
                                : <Button size="sm" variant="ghost" icon={RotateCcw} onClick={() => setModal({ type: "status", student: s })}>Reactivate</Button>}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </TableWrap>
              )}
            </QueryState>
          </div>
        </Card>
      )}
      {modal?.type === "add" && <StudentForm sections={ctSections} onClose={() => setModal(null)} />}
      {modal?.type === "edit" && <StudentForm student={modal.student} sections={ctSections} onClose={() => setModal(null)} />}
      {modal?.type === "status" && <StatusModal student={modal.student} onClose={() => setModal(null)} />}
      {modal?.type === "history" && <HistoryModal student={modal.student} onClose={() => setModal(null)} />}
    </>
  );
}
