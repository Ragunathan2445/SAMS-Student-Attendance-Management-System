import { Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import { SchoolMark } from "../../components/SchoolMark";

export default function AuthShell({ portal, title, subtitle, aside, children }) {
  return (
    <div className="grid min-h-screen bg-white lg:grid-cols-[minmax(0,5fr)_minmax(0,6fr)]">
      <aside className="relative hidden overflow-hidden bg-brand-800 p-10 text-brand-50 lg:flex lg:flex-col">
        <div aria-hidden className="absolute -right-24 -top-24 size-96 rounded-full border-[48px] border-brand-700/60" />
        <div aria-hidden className="absolute -bottom-32 -left-20 size-96 rounded-full border-[36px] border-brand-700/40" />
        <Link to="/" className="relative flex items-center gap-3">
          <SchoolMark size={44} />
          <span className="font-serif text-lg font-semibold">Sri Vidya Mandir School</span>
        </Link>
        <div className="relative mt-auto">
          <p className="text-sm font-semibold uppercase tracking-widest text-brand-300">{portal}</p>
          <h2 className="mt-3 font-serif text-4xl font-semibold leading-tight text-white">{aside?.title}</h2>
          <p className="mt-4 max-w-md text-brand-200">{aside?.text}</p>
        </div>
      </aside>

      <main className="flex flex-col px-4 py-8 sm:px-10">
        <Link to="/" className="inline-flex items-center gap-1.5 self-start text-sm font-medium text-brand-700 hover:text-brand-900">
          <ArrowLeft className="size-4" /> Back to school home
        </Link>
        <div className="mx-auto my-auto w-full max-w-md py-10">
          <div className="mb-8 lg:hidden"><SchoolMark size={44} /></div>
          <p className="text-sm font-semibold uppercase tracking-wider text-brand-600">{portal}</p>
          <h1 className="mt-2 text-3xl font-semibold text-brand-950">{title}</h1>
          {subtitle && <p className="mt-2 text-ink-soft">{subtitle}</p>}
          <div className="mt-8">{children}</div>
        </div>
      </main>
    </div>
  );
}

export function StepDots({ step, total = 2 }) {
  return (
    <div className="mb-6 flex items-center gap-2" aria-label={`Step ${step} of ${total}`}>
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={`h-1.5 rounded-full transition-all ${i + 1 <= step ? "w-10 bg-brand-700" : "w-6 bg-brand-200"}`} />
      ))}
      <span className="ml-2 text-xs font-medium text-muted">Step {step} of {total}</span>
    </div>
  );
}

export function CodeInput({ value, onChange, autoFocus = true, label = "6-digit code" }) {
  return (
    <input
      inputMode="numeric" autoComplete="one-time-code" maxLength={6} autoFocus={autoFocus} aria-label={label}
      value={value} onChange={(e) => onChange(e.target.value.replace(/\D/g, "").slice(0, 6))}
      placeholder="••••••"
      className="field-input num h-14 text-center font-mono text-2xl tracking-[0.6em]"
    />
  );
}
