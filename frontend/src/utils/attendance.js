/**
 * One source of truth for attendance categories: label, colour token and symbol.
 * Colour is never used alone – every status also shows a symbol and a text label.
 */
export const STATUS = {
  present: { label: "Present", color: "var(--color-st-present)", symbol: "✓", tone: "present" },
  partial: { label: "Partial day", color: "var(--color-st-partial)", symbol: "◐", tone: "partial" },
  absent: { label: "Absent", color: "var(--color-st-absent)", symbol: "✕", tone: "absent" },
  approved_leave: { label: "Approved leave", color: "var(--color-st-leave)", symbol: "L", tone: "leave" },
  leave: { label: "Approved leave", color: "var(--color-st-leave)", symbol: "L", tone: "leave" },
  pending_leave: { label: "Pending leave", color: "var(--color-st-pending)", symbol: "P", tone: "pending" },
  school_holiday: { label: "School holiday", color: "var(--color-st-holiday)", symbol: "H", tone: "holiday" },
  festival_holiday: { label: "Festival holiday", color: "var(--color-st-holiday)", symbol: "F", tone: "holiday" },
  weekly_holiday: { label: "Weekly holiday", color: "var(--color-st-holiday)", symbol: "W", tone: "holiday" },
  not_recorded: { label: "Not recorded yet", color: "#d8d0c7", symbol: "–", tone: "muted" },
  not_marked: { label: "Not marked yet", color: "#d8d0c7", symbol: "–", tone: "muted" },
  upcoming: { label: "Upcoming", color: "#ece3d9", symbol: "·", tone: "muted" },
  outside: { label: "Not enrolled", color: "#ece3d9", symbol: "·", tone: "muted" },
};

export const statusMeta = (key) => STATUS[key] || { label: key, color: "#ccc", symbol: "?", tone: "muted" };

/** Chart series in fixed order (validated palette order, never cycled). */
export const PERIOD_SERIES = [
  { key: "present_periods", label: "Present", color: "#0e8a6a" },
  { key: "absent_periods", label: "Absent", color: "#c2412d" },
  { key: "pending_leave_periods", label: "Pending leave", color: "#7b5ea7" },
  { key: "leave_periods", label: "Approved leave", color: "#c98a2b" },
];

export const DAY_SERIES = [
  { key: "present_days", label: "Present", color: "#0e8a6a" },
  { key: "partial_days", label: "Partial day", color: "#7db85a" },
  { key: "absent_days", label: "Absent", color: "#c2412d" },
  { key: "pending_leave_days", label: "Pending leave", color: "#7b5ea7" },
  { key: "approved_leave_days", label: "Approved leave", color: "#c98a2b" },
];

export const ABSENCE_REASONS = {
  fever: "Fever",
  medical_appointment: "Medical appointment",
  family_function: "Family function",
  personal: "Personal reasons",
  informed_leave: "Informed leave",
  uninformed: "Uninformed absence",
  other: "Other reasons",
  not_specified: "Not specified",
};

export const LEAVE_REASONS = {
  fever: "Fever",
  medical_appointment: "Medical appointment",
  family_function: "Family function",
  personal: "Personal reasons",
  other: "Other",
};
