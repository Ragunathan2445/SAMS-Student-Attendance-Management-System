import { forwardRef, useEffect, useState } from "react";
import { AlertCircle, Inbox, Loader2, X } from "lucide-react";
import { errorMessage } from "../../services/api";
import { initials } from "../../utils/format";

const cx = (...c) => c.filter(Boolean).join(" ");
export { cx };

// ------------------------------------------------------------------ Button
const VARIANTS = {
  primary: "bg-brand-700 text-white hover:bg-brand-800 shadow-sm",
  secondary: "border border-brand-300 bg-white text-brand-800 hover:bg-brand-50",
  ghost: "text-brand-800 hover:bg-brand-50",
  danger: "bg-[#a8361f] text-white hover:bg-[#8f2c18]",
  subtle: "bg-brand-50 text-brand-800 hover:bg-brand-100",
};
export const Button = forwardRef(function Button(
  { variant = "primary", size = "md", loading, icon: Icon, className, children, disabled, ...rest },
  ref,
) {
  const sizes = { sm: "h-8 px-3 text-sm gap-1.5", md: "h-10 px-4 text-[15px] gap-2", lg: "h-12 px-6 text-base gap-2" };
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={cx(
        "inline-flex items-center justify-center rounded-lg font-medium transition disabled:cursor-not-allowed disabled:opacity-55",
        VARIANTS[variant],
        sizes[size],
        className,
      )}
      {...rest}
    >
      {loading ? <Loader2 className="size-4 animate-spin" /> : Icon ? <Icon className="size-4" /> : null}
      {children}
    </button>
  );
});

// ------------------------------------------------------------------ Card
export function Card({ title, subtitle, action, children, className, bodyClass = "p-5" }) {
  return (
    <section className={cx("card", className)}>
      {(title || action) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            {title && <h2 className="text-lg font-semibold text-ink">{title}</h2>}
            {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function PageHeader({ title, description, actions }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-ink sm:text-[28px]">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-ink-soft">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

// ------------------------------------------------------------------ Badge
const TONES = {
  neutral: "bg-brand-50 text-brand-800 ring-brand-200",
  present: "bg-[#e7f4ef] text-[#0a6a51] ring-[#b9e0d2]",
  partial: "bg-[#eef6e7] text-[#4d7a31] ring-[#cfe5bf]",
  absent: "bg-[#fbebe8] text-[#a3341f] ring-[#f1c6bd]",
  leave: "bg-[#fbf1e2] text-[#8f5f14] ring-[#ecd3a8]",
  pending: "bg-[#f1ecf7] text-[#5f4590] ring-[#d6cbe8]",
  holiday: "bg-[#f3f1ee] text-[#6d645b] ring-[#ddd6ce]",
  muted: "bg-[#f6f3ef] text-muted ring-line",
  success: "bg-[#e7f4ef] text-[#0a6a51] ring-[#b9e0d2]",
  warning: "bg-[#fbf1e2] text-[#8f5f14] ring-[#ecd3a8]",
  danger: "bg-[#fbebe8] text-[#a3341f] ring-[#f1c6bd]",
};
export function Badge({ tone = "neutral", children, className }) {
  return (
    <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", TONES[tone] || TONES.neutral, className)}>
      {children}
    </span>
  );
}

const STATUS_TONES = { pending: "pending", approved: "success", rejected: "danger", paid: "success", processing: "warning",
  success: "success", failed: "danger", active: "success", inactive: "muted", due: "neutral", overdue: "danger",
  partially_paid: "warning", partially_paid_overdue: "danger", on_hold: "warning" };
export function StatusPill({ status, label }) {
  return <Badge tone={STATUS_TONES[status] || "neutral"}>{label || String(status).replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase())}</Badge>;
}

// ------------------------------------------------------------------ Form fields
export function Field({ label, error, hint, children, required, className }) {
  return (
    <label className={cx("block", className)}>
      {label && (
        <span className="mb-1.5 block text-sm font-medium text-ink-soft">
          {label} {required && <span className="text-[#a8361f]">*</span>}
        </span>
      )}
      {children}
      {error ? <span className="mt-1 block text-xs text-[#a8361f]">{error}</span> : hint ? <span className="mt-1 block text-xs text-muted">{hint}</span> : null}
    </label>
  );
}
export const Input = forwardRef(function Input({ className, ...p }, ref) {
  return <input ref={ref} className={cx("field-input", className)} {...p} />;
});
export const Select = forwardRef(function Select({ className, children, ...p }, ref) {
  return (
    <select ref={ref} className={cx("field-input pr-8", className)} {...p}>
      {children}
    </select>
  );
});
export const Textarea = forwardRef(function Textarea({ className, ...p }, ref) {
  return <textarea ref={ref} className={cx("field-input min-h-[90px]", className)} {...p} />;
});

// ------------------------------------------------------------------ Feedback states
export function Spinner({ label = "Loading…", className }) {
  return (
    <div className={cx("flex items-center justify-center gap-2 py-12 text-muted", className)}>
      <Loader2 className="size-5 animate-spin text-brand-600" /> <span className="text-sm">{label}</span>
    </div>
  );
}
export function EmptyState({ icon: Icon = Inbox, title, children }) {
  return (
    <div className="flex flex-col items-center justify-center px-4 py-12 text-center">
      <div className="mb-3 grid size-12 place-items-center rounded-full bg-brand-50 text-brand-600"><Icon className="size-6" /></div>
      <p className="font-medium text-ink">{title}</p>
      {children && <div className="mt-1 max-w-md text-sm text-muted">{children}</div>}
    </div>
  );
}
export function ErrorState({ error, onRetry }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-xl border border-[#f1c6bd] bg-[#fdf5f3] px-4 py-8 text-center">
      <AlertCircle className="size-6 text-[#a8361f]" />
      <p className="text-sm text-[#7d2a19]">{errorMessage(error)}</p>
      {onRetry && <Button size="sm" variant="secondary" onClick={onRetry}>Try again</Button>}
    </div>
  );
}
export function QueryState({ query, children, empty, emptyTitle = "Nothing to show yet" }) {
  if (query.isLoading) return <Spinner />;
  if (query.isError) return <ErrorState error={query.error} onRetry={() => query.refetch()} />;
  if (empty) return <EmptyState title={emptyTitle} />;
  return children;
}

// ------------------------------------------------------------------ Modal
export function Modal({ open, onClose, title, children, footer, width = "max-w-lg" }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => e.key === "Escape" && onClose?.();
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-brand-950/40 p-0 backdrop-blur-[2px] sm:items-center sm:p-4" onMouseDown={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title}
        className={cx("flex max-h-[92vh] w-full flex-col rounded-t-2xl bg-white shadow-2xl sm:rounded-2xl", width)}
        onMouseDown={(e) => e.stopPropagation()}>
        <header className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-brand-50 hover:text-ink" aria-label="Close"><X className="size-5" /></button>
        </header>
        <div className="overflow-y-auto px-5 py-4">{children}</div>
        {footer && <footer className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">{footer}</footer>}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ Tabs (segmented)
export function Tabs({ tabs, value, onChange, className }) {
  return (
    <div role="tablist" className={cx("inline-flex max-w-full overflow-x-auto rounded-xl border border-line bg-brand-50 p-1", className)}>
      {tabs.map((t) => (
        <button key={t.value} role="tab" aria-selected={value === t.value} onClick={() => onChange(t.value)}
          className={cx("flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-lg px-3.5 py-1.5 text-sm font-medium transition",
            value === t.value ? "bg-white text-brand-800 shadow-sm ring-1 ring-brand-200" : "text-ink-soft hover:text-brand-800")}>
          {t.icon && <t.icon className="size-4" />}
          {t.label}
          {t.count ? <span className="ml-0.5 rounded-full bg-brand-700 px-1.5 text-[11px] text-white">{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

// ------------------------------------------------------------------ Stat tile
export function StatTile({ label, value, sub, accent, icon: Icon }) {
  return (
    <div className="card relative overflow-hidden p-4">
      {accent && <span className="absolute inset-y-0 left-0 w-1" style={{ background: accent }} />}
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
        {Icon && <Icon className="size-4 text-brand-400" />}
      </div>
      <p className="num mt-1.5 text-2xl font-semibold text-ink">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-muted">{sub}</p>}
    </div>
  );
}

// ------------------------------------------------------------------ Avatar (authorised photo)
export function Avatar({ src, name, size = 40, className, rounded = "rounded-full" }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [src]);
  const style = { width: size, height: size };
  if (!src || failed) {
    return (
      <span style={style} className={cx("grid shrink-0 place-items-center bg-brand-100 font-semibold text-brand-700", rounded, className)}>
        <span style={{ fontSize: size * 0.36 }}>{initials(name)}</span>
      </span>
    );
  }
  return <img src={src} alt={name ? `Photo of ${name}` : ""} style={style} onError={() => setFailed(true)}
    className={cx("shrink-0 object-cover ring-1 ring-line", rounded, className)} loading="lazy" />;
}

export function InfoRow({ label, value }) {
  return (
    <div className="flex flex-col gap-0.5 py-2 sm:flex-row sm:gap-4">
      <dt className="w-44 shrink-0 text-sm text-muted">{label}</dt>
      <dd className="text-[15px] font-medium text-ink">{value || <span className="text-muted">—</span>}</dd>
    </div>
  );
}

export function TableWrap({ children }) {
  return <div className="-mx-5 overflow-x-auto px-5">{children}</div>;
}
