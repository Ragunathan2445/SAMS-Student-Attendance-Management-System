import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { format, getDay, parseISO } from "date-fns";
import { CalendarCheck2, CalendarX2, Clock3, Percent, Plane, Sun } from "lucide-react";
import { Badge, StatTile, cx } from "../ui";
import { DAY_SERIES, PERIOD_SERIES, statusMeta } from "../../utils/attendance";
import { pct } from "../../utils/format";

// ------------------------------------------------------------------ status badge
export function AttendanceBadge({ status, withSymbol = true }) {
  const m = statusMeta(status);
  return (
    <Badge tone={m.tone}>
      {withSymbol && <span aria-hidden className="font-bold">{m.symbol}</span>}
      {m.label}
    </Badge>
  );
}

export function Legend({ series, extra = [] }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-soft" aria-label="Legend">
      {[...series, ...extra].map((s) => (
        <li key={s.label} className="flex items-center gap-1.5">
          <span className="size-2.5 rounded-sm" style={{ background: s.color }} />{s.label}
        </li>
      ))}
    </ul>
  );
}

function ChartTooltip({ active, payload, label, unit, labelFormatter }) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  const items = payload.filter((p) => p.value > 0 && p.dataKey !== "holiday");
  return (
    <div className="min-w-[170px] rounded-xl border border-line bg-white px-3 py-2.5 text-xs shadow-lg">
      <p className="mb-1.5 font-semibold text-ink">{labelFormatter ? labelFormatter(label, row) : label}</p>
      {row.holidayLabel && <p className="text-muted">{row.holidayLabel}</p>}
      {items.map((p) => (
        <p key={p.dataKey} className="flex items-center justify-between gap-4 py-0.5">
          <span className="flex items-center gap-1.5 text-ink-soft"><span className="size-2 rounded-sm" style={{ background: p.color }} />{p.name}</span>
          <span className="num font-semibold text-ink">{p.value} {unit}</span>
        </p>
      ))}
      {!items.length && !row.holidayLabel && <p className="text-muted">No attendance recorded</p>}
    </div>
  );
}

function StackedBars({ data, series, xKey, unit, height = 260, labelFormatter, holidayKey }) {
  return (
    <div style={{ height }} className="w-full">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }} barCategoryGap="28%">
          <CartesianGrid vertical={false} stroke="#f0e9e1" />
          <XAxis dataKey={xKey} tickLine={false} axisLine={{ stroke: "#e2d7cb" }} interval={0} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} width={44} />
          <Tooltip content={<ChartTooltip unit={unit} labelFormatter={labelFormatter} />} cursor={{ fill: "#fbf7f3" }} />
          {holidayKey && <Bar dataKey={holidayKey} name="Holiday" stackId="a" fill="#e9e3dc" stroke="#fff" strokeWidth={2} isAnimationActive={false} />}
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} stackId="a" fill={s.color} stroke="#fff" strokeWidth={2}
              radius={i === series.length - 1 ? [4, 4, 0, 0] : 0} isAnimationActive={false} maxBarSize={44} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

// ------------------------------------------------------------------ summary tiles
export function SummaryTiles({ summary }) {
  if (!summary) return null;
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <StatTile label="Attendance (days)" value={pct(summary.daily_percentage)} sub={`Period-wise ${pct(summary.period_percentage)}`} icon={Percent} accent="#6f4529" />
      <StatTile label="Present days" value={summary.present_days} sub={summary.partial_days ? `+ ${summary.partial_days} partial day(s)` : "Full days"} icon={CalendarCheck2} accent="var(--color-st-present)" />
      <StatTile label="Absent days" value={summary.absent_days} sub="Holidays never count" icon={CalendarX2} accent="var(--color-st-absent)" />
      <StatTile label="Approved leave" value={summary.approved_leave_days} sub="Shown separately" icon={Plane} accent="var(--color-st-leave)" />
      <StatTile label="Pending leave" value={summary.pending_leave_days} sub="Awaiting teacher" icon={Clock3} accent="var(--color-st-pending)" />
      <StatTile label="Working days" value={summary.total_working_days}
        sub={summary.not_recorded_days ? `${summary.not_recorded_days} not recorded yet` : `${(summary.school_holidays || 0) + (summary.festival_holidays || 0)} holidays excluded`} icon={Sun} accent="#bc8d63" />
    </div>
  );
}

// ------------------------------------------------------------------ weekly
export function WeeklyChart({ days }) {
  const data = days.map((d) => {
    const m = statusMeta(d.category);
    const holiday = !["present", "partial", "absent", "approved_leave", "pending_leave", "not_recorded", "upcoming", "outside"].includes(d.category);
    return {
      label: format(parseISO(d.date), "EEE d"),
      date: d.date,
      ...Object.fromEntries(PERIOD_SERIES.map((s) => [s.key, d[s.key]])),
      holiday: holiday ? 7 : 0,
      holidayLabel: holiday ? `${m.label}${d.title ? ` – ${d.title}` : ""}` : d.category === "upcoming" ? "Upcoming day" : null,
    };
  });
  return (
    <div className="space-y-3">
      <StackedBars data={data} series={PERIOD_SERIES} xKey="label" unit="periods" holidayKey="holiday"
        labelFormatter={(_, row) => format(parseISO(row.date), "EEEE, d MMM")} />
      <Legend series={PERIOD_SERIES} extra={[{ label: "Holiday", color: "#e9e3dc" }]} />
    </div>
  );
}

// ------------------------------------------------------------------ yearly
export function YearlyChart({ months }) {
  const data = months.map((mo) => ({ ...mo, short: mo.label.split(" ")[0] }));
  return (
    <div className="space-y-3">
      <StackedBars data={data} series={DAY_SERIES} xKey="short" unit="days" height={280}
        labelFormatter={(_, row) => `${row.label} · ${pct(row.daily_percentage)}`} />
      <Legend series={DAY_SERIES} />
    </div>
  );
}

// ------------------------------------------------------------------ monthly
export function CompositionBar({ summary }) {
  const parts = DAY_SERIES.map((s) => ({ ...s, value: summary[s.key] || 0 })).filter((p) => p.value > 0);
  const total = parts.reduce((a, p) => a + p.value, 0);
  if (!total) return <p className="text-sm text-muted">No attendance recorded in this month yet.</p>;
  return (
    <div>
      <div className="flex h-4 w-full gap-[2px] overflow-hidden rounded-md" role="img" aria-label="Share of working days by status">
        {parts.map((p) => (
          <div key={p.key} title={`${p.label}: ${p.value} day(s)`} style={{ width: `${(p.value / total) * 100}%`, background: p.color }} />
        ))}
      </div>
      <ul className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-5">
        {parts.map((p) => (
          <li key={p.key} className="flex items-center gap-2"><span className="size-2.5 rounded-sm" style={{ background: p.color }} />
            <span className="text-ink-soft">{p.label}</span><b className="num ml-auto text-ink sm:ml-1">{p.value}</b></li>
        ))}
      </ul>
    </div>
  );
}

export function MonthCalendar({ days, onSelect, selected }) {
  if (!days?.length) return null;
  const first = parseISO(days[0].date);
  const offset = (getDay(first) + 6) % 7; // Monday first
  const cells = [...Array(offset).fill(null), ...days];
  return (
    <div>
      <div className="grid grid-cols-7 gap-1.5 text-center text-[11px] font-semibold uppercase tracking-wide text-muted">
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((d) => <div key={d}>{d}</div>)}
      </div>
      <div className="mt-1.5 grid grid-cols-7 gap-1.5">
        {cells.map((d, i) => {
          if (!d) return <div key={`e${i}`} />;
          const m = statusMeta(d.category);
          const strong = ["present", "partial", "absent", "approved_leave", "pending_leave"].includes(d.category);
          return (
            <button key={d.date} type="button" onClick={() => onSelect?.(d)}
              title={`${format(parseISO(d.date), "EEE d MMM")}: ${m.label}${d.title ? ` – ${d.title}` : ""}`}
              className={cx("relative flex aspect-square min-h-10 flex-col items-center justify-center rounded-lg text-sm transition hover:ring-2 hover:ring-brand-300",
                selected === d.date && "ring-2 ring-brand-700")}
              style={{ background: strong ? m.color : m.color, color: strong ? "#fff" : "#5c4d40", opacity: d.category === "upcoming" || d.category === "outside" ? 0.6 : 1 }}>
              <span className="num font-semibold">{parseISO(d.date).getDate()}</span>
              <span aria-hidden className="text-[10px] leading-none opacity-90">{m.symbol}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function CalendarLegend() {
  const keys = ["present", "partial", "absent", "approved_leave", "pending_leave", "school_holiday", "festival_holiday", "weekly_holiday", "not_recorded"];
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-ink-soft">
      {keys.map((k) => {
        const m = statusMeta(k);
        return <li key={k} className="flex items-center gap-1.5"><span className="grid size-4 place-items-center rounded text-[9px] font-bold text-white" style={{ background: m.color }}>{m.symbol}</span>{m.label}</li>;
      })}
    </ul>
  );
}
