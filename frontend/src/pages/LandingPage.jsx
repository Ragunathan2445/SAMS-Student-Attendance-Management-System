import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Award, BookOpen, CalendarCheck, GraduationCap, Mail, MapPin, Phone, ShieldCheck, Users } from "lucide-react";
import { SchoolName } from "../components/SchoolMark";
import { publicApi } from "../services/endpoints";

const FALLBACK = {
  name: "Sri Vidya Mandir School",
  tagline: "Learning with discipline, growing with values",
  about: "A co-educational school serving families since 1998, combining strong academics with sports, arts and community service.",
  highlights: [],
  address: "Chennai, Tamil Nadu",
  phone: "",
  email: "",
};

function PortalCard({ to, icon: Icon, title, text, points }) {
  return (
    <Link to={to}
      className="group relative flex flex-col overflow-hidden rounded-2xl border border-brand-200 bg-white p-6 shadow-[0_1px_0_#ece3d9] transition hover:-translate-y-0.5 hover:border-brand-400 hover:shadow-[0_12px_30px_-12px_rgba(111,69,41,0.35)] sm:p-7">
      <span className="absolute inset-x-0 top-0 h-1 bg-brand-700 opacity-0 transition group-hover:opacity-100" />
      <div className="flex items-center gap-4">
        <span className="grid size-12 place-items-center rounded-xl bg-brand-700 text-white"><Icon className="size-6" /></span>
        <h2 className="text-2xl font-semibold text-brand-900">{title}</h2>
      </div>
      <p className="mt-4 text-ink-soft">{text}</p>
      <ul className="mt-4 space-y-1.5 text-sm text-ink-soft">
        {points.map((p) => (
          <li key={p} className="flex items-center gap-2"><span className="size-1.5 rounded-full bg-brand-400" />{p}</li>
        ))}
      </ul>
      <span className="mt-6 inline-flex items-center gap-2 font-semibold text-brand-700">
        Sign in <ArrowRight className="size-4 transition group-hover:translate-x-1" />
      </span>
    </Link>
  );
}

export default function LandingPage() {
  const { data } = useQuery({ queryKey: ["school"], queryFn: publicApi.school, staleTime: 300_000, retry: 0 });
  const school = { ...FALLBACK, ...(data?.configured ? data : {}) };
  const year = new Date().getFullYear();

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-line">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <SchoolName name={school.name} sub={school.tagline} />
          <nav className="hidden items-center gap-6 text-sm font-medium text-ink-soft md:flex" aria-label="Page sections">
            <a href="#about" className="hover:text-brand-700">About</a>
            <a href="#contact" className="hover:text-brand-700">Contact</a>
          </nav>
        </div>
      </header>

      <section className="relative overflow-hidden">
        <div aria-hidden className="pointer-events-none absolute inset-0 opacity-[0.55]"
          style={{ backgroundImage: "linear-gradient(#f4ebe1 1px, transparent 1px), linear-gradient(90deg, #f4ebe1 1px, transparent 1px)", backgroundSize: "44px 44px", maskImage: "linear-gradient(to bottom, black, transparent 85%)" }} />
        <div className="relative mx-auto max-w-6xl px-4 pb-14 pt-12 sm:px-6 sm:pt-16">
          <p className="inline-flex items-center gap-2 rounded-full border border-brand-200 bg-white px-3 py-1 text-xs font-semibold uppercase tracking-wider text-brand-700">
            <CalendarCheck className="size-3.5" /> School Attendance Management System
          </p>
          <h1 className="mt-5 max-w-3xl text-4xl font-semibold leading-tight text-brand-950 sm:text-5xl">
            Welcome to {school.name}
          </h1>
          <p className="mt-4 max-w-2xl text-lg text-ink-soft">{school.about}</p>

          <div className="mt-10 grid gap-5 md:grid-cols-2">
            <PortalCard to="/parent/login" icon={Users} title="Parent Portal"
              text="Follow your child's attendance, request leave, and view fees and receipts."
              points={["Sign in with your registered mobile/e-mail and your child's roll number", "One-time password (OTP) verification", "Daily, weekly, monthly and yearly attendance"]} />
            <PortalCard to="/teacher/login" icon={GraduationCap} title="Teacher Portal"
              text="Mark period-wise attendance, approve leave and substitute submissions, and view salary slips."
              points={["Teacher ID or e-mail with password", "Google Authenticator verification", "Separate morning and afternoon sessions"]} />
          </div>
        </div>
      </section>

      <section id="about" className="border-y border-line bg-brand-50/50">
        <div className="mx-auto grid max-w-6xl gap-10 px-4 py-14 sm:px-6 md:grid-cols-[1.2fr_1fr]">
          <div>
            <h2 className="text-3xl font-semibold text-brand-950">About our school</h2>
            <p className="mt-4 text-ink-soft">{school.about}</p>
            {school.highlights?.length > 0 && (
              <ul className="mt-6 grid gap-3 sm:grid-cols-2">
                {school.highlights.map((h) => (
                  <li key={h} className="flex items-start gap-2.5 rounded-xl border border-line bg-white px-3.5 py-3 text-sm text-ink">
                    <BookOpen className="mt-0.5 size-4 shrink-0 text-brand-600" />{h}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <dl className="grid grid-cols-2 gap-4 self-start">
            {[
              { label: "Established", value: school.established_year, icon: Award },
              { label: "Principal", value: school.principal_name, icon: GraduationCap },
              { label: "Students (demo)", value: school.stats?.students, icon: Users },
              { label: "Teachers (demo)", value: school.stats?.teachers, icon: ShieldCheck },
            ].map((f) => (
              <div key={f.label} className="rounded-2xl border border-line bg-white p-4">
                <f.icon className="size-5 text-brand-500" />
                <dt className="mt-3 text-xs font-semibold uppercase tracking-wide text-muted">{f.label}</dt>
                <dd className="mt-1 font-serif text-xl font-semibold text-brand-900">{f.value ?? "—"}</dd>
              </div>
            ))}
            {school.affiliation && <p className="col-span-2 text-xs text-muted">{school.affiliation}</p>}
          </dl>
        </div>
      </section>

      <section id="contact" className="mx-auto max-w-6xl px-4 py-14 sm:px-6">
        <h2 className="text-3xl font-semibold text-brand-950">Contact us</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <div className="card flex gap-3 p-5"><MapPin className="size-5 shrink-0 text-brand-600" /><div><p className="text-sm font-semibold">Address</p><p className="mt-1 text-sm text-ink-soft">{school.address}</p></div></div>
          <div className="card flex gap-3 p-5"><Phone className="size-5 shrink-0 text-brand-600" /><div><p className="text-sm font-semibold">Phone</p>{school.phone ? <a href={`tel:${school.phone.replace(/\s/g, "")}`} className="mt-1 block text-sm text-brand-700 hover:underline">{school.phone}</a> : <p className="text-sm text-muted">—</p>}</div></div>
          <div className="card flex gap-3 p-5"><Mail className="size-5 shrink-0 text-brand-600" /><div><p className="text-sm font-semibold">E-mail</p>{school.email ? <a href={`mailto:${school.email}`} className="mt-1 block break-all text-sm text-brand-700 hover:underline">{school.email}</a> : <p className="text-sm text-muted">—</p>}</div></div>
        </div>
      </section>

      <footer className="border-t border-line bg-brand-900 text-brand-100">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-6 text-sm sm:px-6">
          <p>© {year} {school.name}</p>
          <p className="text-brand-300">Demonstration build · all student, parent and financial data is synthetic</p>
        </div>
      </footer>
    </div>
  );
}
