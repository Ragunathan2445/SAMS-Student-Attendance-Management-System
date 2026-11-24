import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Lock, Mail, MapPin, Phone, Search } from "lucide-react";
import { Avatar, Button, Card, EmptyState, Field, Input, PageHeader, QueryState, Select } from "../../components/ui";
import { teacherApi } from "../../services/endpoints";

export default function StudentDirectory() {
  const sectionsQ = useQuery({ queryKey: ["teacher", "sections"], queryFn: teacherApi.sections });
  const sections = sectionsQ.data?.sections || [];
  const classes = [...new Set(sections.map((s) => s.class_name))];
  const [klass, setKlass] = useState("");
  const [section, setSection] = useState("");
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const q = useQuery({ queryKey: ["teacher", "directory", section, term], queryFn: () => teacherApi.directory({ section_id: section, q: term }) });
  const list = (q.data?.students || []).filter((s) => !klass || section || s.class_label.startsWith(klass));

  return (
    <>
      <PageHeader title="Student Details" description="Emergency contact information for students in your assigned classes. Please use it only for school purposes." />
      <Card bodyClass="p-0">
        <form className="flex flex-wrap items-end gap-3 border-b border-line p-4" onSubmit={(e) => { e.preventDefault(); setTerm(search); }}>
          <Field label="Class" className="min-w-[140px]">
            <Select value={klass} onChange={(e) => { setKlass(e.target.value); setSection(""); }}><option value="">All</option>{classes.map((c) => <option key={c}>{c}</option>)}</Select>
          </Field>
          <Field label="Section" className="min-w-[120px]">
            <Select value={section} onChange={(e) => setSection(e.target.value)} disabled={!klass}>
              <option value="">All</option>{sections.filter((s) => s.class_name === klass).map((s) => <option key={s.id} value={s.id}>{s.section_name}</option>)}
            </Select>
          </Field>
          <Field label="Student name or roll number" className="min-w-[220px] flex-1"><Input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="e.g. Meera or 6A07" /></Field>
          <Button type="submit" icon={Search}>Search</Button>
        </form>
        <div className="p-5">
          <QueryState query={q}>
            {!list.length ? <EmptyState title="No students found in your authorised classes" /> : (
              <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {list.map((s) => (
                  <li key={s.id} className="rounded-2xl border border-line p-4">
                    <div className="flex items-center gap-3">
                      <Avatar src={s.photo_url} name={s.full_name} size={56} rounded="rounded-xl" />
                      <div className="min-w-0"><p className="truncate font-semibold">{s.full_name}</p><p className="text-sm text-muted">Roll {s.roll_number} · {s.class_label}</p></div>
                    </div>
                    <dl className="mt-4 space-y-2 text-sm">
                      <div className="flex items-center gap-2"><Phone className="size-4 shrink-0 text-brand-500" /><a href={`tel:${s.parent_mobile}`} className="font-semibold text-brand-800 hover:underline">{s.parent_mobile}</a><span className="truncate text-muted">· {s.parent_name}</span></div>
                      <div className="flex items-center gap-2 break-all"><Mail className="size-4 shrink-0 text-brand-500" /><a href={`mailto:${s.parent_email}`} className="hover:underline">{s.parent_email}</a></div>
                      <div className="flex items-start gap-2 text-ink-soft"><MapPin className="mt-0.5 size-4 shrink-0 text-brand-500" />{s.address}</div>
                    </dl>
                  </li>
                ))}
              </ul>
            )}
          </QueryState>
          <p className="mt-5 flex items-center gap-2 text-xs text-muted"><Lock className="size-3.5" /> Access is limited to sections in your timetable or class-teacher responsibility, and is not available publicly.</p>
        </div>
      </Card>
    </>
  );
}
