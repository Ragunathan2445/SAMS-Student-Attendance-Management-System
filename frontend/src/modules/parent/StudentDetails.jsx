import { useQuery } from "@tanstack/react-query";
import { Bus, Droplet, Mail, MapPin, Phone, UserRound } from "lucide-react";
import { useSelectedStudent } from "./ParentPortal";
import { Avatar, Badge, Card, InfoRow, PageHeader, QueryState, StatusPill } from "../../components/ui";
import { parentApi } from "../../services/endpoints";
import { fmtDate } from "../../utils/format";

export default function StudentDetails() {
  const { student } = useSelectedStudent();
  const query = useQuery({ queryKey: ["parent", "profile", student.id], queryFn: () => parentApi.profile(student.id) });
  const p = query.data;

  return (
    <>
      <PageHeader title="Student Details" description="Please check that this is your child's correct profile. Contact the school office if anything needs to be changed." />
      <QueryState query={query}>
        {p && (
          <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
            <div className="card overflow-hidden">
              <div className="h-20 bg-brand-700" />
              <div className="-mt-12 flex flex-col items-center px-5 pb-6 text-center">
                <Avatar src={p.photo_url} name={p.full_name} size={112} rounded="rounded-2xl" className="ring-4 ring-white" />
                <h2 className="mt-3 text-2xl font-semibold">{p.full_name}</h2>
                <p className="text-sm text-muted">{p.class_name} – Section {p.section_name}</p>
                <div className="mt-3 flex flex-wrap justify-center gap-2">
                  <Badge>Roll {p.roll_number}</Badge>
                  <StatusPill status={p.status} />
                </div>
                <dl className="mt-5 grid w-full grid-cols-2 gap-3 text-left">
                  <div className="rounded-xl bg-brand-50 p-3"><dt className="text-xs text-muted">Academic year</dt><dd className="font-semibold">{p.academic_year}</dd></div>
                  <div className="rounded-xl bg-brand-50 p-3"><dt className="flex items-center gap-1 text-xs text-muted"><Droplet className="size-3" />Blood group</dt><dd className="font-semibold">{p.blood_group || "—"}</dd></div>
                  <div className="rounded-xl bg-brand-50 p-3"><dt className="text-xs text-muted">Class teacher</dt><dd className="text-sm font-semibold">{p.class_teacher || "—"}</dd></div>
                  <div className="rounded-xl bg-brand-50 p-3"><dt className="flex items-center gap-1 text-xs text-muted"><Bus className="size-3" />School bus</dt><dd className="font-semibold">{p.uses_school_bus ? "Yes" : "No"}</dd></div>
                </dl>
              </div>
            </div>

            <div className="space-y-6">
              <Card title="Personal information">
                <dl className="divide-y divide-line">
                  <InfoRow label="Full name" value={p.full_name} />
                  <InfoRow label="Roll number" value={p.roll_number} />
                  <InfoRow label="Admission number" value={p.admission_number} />
                  <InfoRow label="Date of birth" value={fmtDate(p.date_of_birth)} />
                  <InfoRow label="Gender" value={p.gender} />
                  <InfoRow label="Class & section" value={`${p.class_name} – ${p.section_name}${p.room ? ` (${p.room})` : ""}`} />
                  <InfoRow label="Admission date" value={fmtDate(p.admission_date)} />
                  <InfoRow label="Student contact" value={p.contact_number} />
                  <InfoRow label="Address" value={p.address} />
                </dl>
              </Card>
              <Card title="Parent / guardian information">
                <div className="grid gap-4 md:grid-cols-2">
                  {p.guardians.map((g) => (
                    <div key={g.email} className="rounded-xl border border-line p-4">
                      <div className="flex items-center gap-3">
                        <span className="grid size-10 place-items-center rounded-full bg-brand-100 text-brand-700"><UserRound className="size-5" /></span>
                        <div>
                          <p className="font-semibold">{g.name}</p>
                          <p className="text-xs text-muted">{g.relation}{g.is_primary ? " · Primary contact" : ""}{g.occupation ? ` · ${g.occupation}` : ""}</p>
                        </div>
                      </div>
                      <ul className="mt-3 space-y-1.5 text-sm text-ink-soft">
                        <li className="flex items-center gap-2"><Phone className="size-4 text-brand-500" />{g.mobile}</li>
                        <li className="flex items-center gap-2 break-all"><Mail className="size-4 shrink-0 text-brand-500" />{g.email}</li>
                        <li className="flex items-start gap-2"><MapPin className="mt-0.5 size-4 shrink-0 text-brand-500" />{g.address || "—"}</li>
                      </ul>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        )}
      </QueryState>
    </>
  );
}
