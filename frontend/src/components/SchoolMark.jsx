export function SchoolMark({ size = 40, className = "" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" className={className} aria-hidden="true">
      <rect width="64" height="64" rx="16" fill="#6F4529" />
      <path d="M32 11 51 19.5V24H13v-4.5z" fill="#F4EBE1" />
      <path d="M18 27h6v17h-6zm11 0h6v17h-6zm11 0h6v17h-6z" fill="#F4EBE1" />
      <path d="M13 47h38v5H13z" fill="#F4EBE1" />
    </svg>
  );
}

export function SchoolName({ name = "Sri Vidya Mandir School", sub = "Attendance & Parent Portal", light }) {
  return (
    <div className="flex items-center gap-3">
      <SchoolMark size={40} />
      <div className="leading-tight">
        <p className={`font-serif text-[17px] font-semibold ${light ? "text-white" : "text-brand-900"}`}>{name}</p>
        <p className={`text-xs ${light ? "text-brand-200" : "text-muted"}`}>{sub}</p>
      </div>
    </div>
  );
}
