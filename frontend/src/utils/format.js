import { format, parseISO } from "date-fns";

/** Money arrives from the API as decimal strings – format without float arithmetic. */
export function formatINR(value) {
  if (value === null || value === undefined || value === "") return "—";
  const str = String(value);
  const negative = str.startsWith("-");
  const [whole, frac = "00"] = str.replace("-", "").split(".");
  let head = whole.slice(0, -3);
  const tail = whole.slice(-3);
  const groups = [];
  while (head.length > 2) {
    groups.unshift(head.slice(-2));
    head = head.slice(0, -2);
  }
  if (head) groups.unshift(head);
  const grouped = [...groups, tail].filter(Boolean).join(",");
  return `${negative ? "−" : ""}₹${grouped}.${frac.padEnd(2, "0").slice(0, 2)}`;
}

/** Display-only comparison (no arithmetic is done on money in the browser). */
export const isPositive = (value) => Number(value) > 0;

export function fmtDate(value, pattern = "dd MMM yyyy") {
  if (!value) return "—";
  try {
    return format(typeof value === "string" ? parseISO(value) : value, pattern);
  } catch {
    return String(value);
  }
}

export const fmtDateTime = (v) => fmtDate(v, "dd MMM yyyy, hh:mm a");

export function pct(value) {
  if (value === null || value === undefined) return "—";
  return `${Number(value).toFixed(1)}%`;
}

export const todayISO = () => format(new Date(), "yyyy-MM-dd");

export function titleCase(value = "") {
  return String(value).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function initials(name = "") {
  return name.split(" ").slice(0, 2).map((p) => p[0]).join("").toUpperCase();
}
