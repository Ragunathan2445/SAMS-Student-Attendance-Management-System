import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CalendarDays, ClipboardList, History, IdCard, Wallet } from "lucide-react";
import PortalLayout from "../../layouts/PortalLayout";
import { Avatar, ErrorState, Spinner, StatusPill, cx } from "../../components/ui";
import { parentApi } from "../../services/endpoints";

const NAV = [
  { to: "/parent/student", label: "Student Details", icon: IdCard },
  { to: "/parent/attendance", label: "Attendance", icon: CalendarDays },
  { to: "/parent/leave", label: "Leave Information", icon: ClipboardList },
  { to: "/parent/payments", label: "Payment & Receipts", icon: Wallet },
  { to: "/parent/history", label: "History", icon: History },
];
const KEY = "sams.parent.selectedStudent";

function readSelected() {
  try {
    return Number(sessionStorage.getItem(KEY)) || null;
  } catch {
    return null;
  }
}

export default function ParentPortal() {
  const query = useQuery({ queryKey: ["parent", "students"], queryFn: parentApi.students });
  const [selectedId, setSelectedId] = useState(readSelected);
  const students = query.data?.students || [];
  const student = students.find((s) => s.id === selectedId) || students[0];

  useEffect(() => {
    if (!student) return;
    try {
      sessionStorage.setItem(KEY, String(student.id)); // UI convenience only – no auth data
    } catch {
      /* ignore */
    }
  }, [student]);

  const switcher = students.length > 0 && (
    <div className="flex items-center gap-2 overflow-x-auto">
      {students.map((s) => (
        <button key={s.id} onClick={() => setSelectedId(s.id)}
          className={cx("flex shrink-0 items-center gap-2 rounded-full border py-1 pl-1 pr-3 text-sm transition",
            s.id === student?.id ? "border-brand-600 bg-brand-50 text-brand-900" : "border-line text-ink-soft hover:border-brand-300")}>
          <Avatar src={s.photo_url} name={s.full_name} size={28} />
          <span className="font-medium">{s.full_name.split(" ")[0]}</span>
          <span className="hidden text-xs text-muted sm:inline">{s.class_label}</span>
        </button>
      ))}
    </div>
  );

  let content;
  if (query.isLoading) content = <Spinner />;
  else if (query.isError) content = <ErrorState error={query.error} onRetry={query.refetch} />;
  else if (!student) content = <ErrorState error={{ response: { data: { detail: "No student is linked to this account." } } }} />;

  return (
    <PortalLayout portalLabel="Parent Portal" nav={NAV} context={switcher} outletContext={{ student, students }}
      sidebarExtra={student && (
        <div className="flex items-center gap-3 rounded-xl border border-line p-3">
          <Avatar src={student.photo_url} name={student.full_name} size={44} />
          <div className="min-w-0">
            <p className="truncate font-semibold">{student.full_name}</p>
            <p className="text-xs text-muted">{student.class_label} · Roll {student.roll_number}</p>
            {student.status !== "active" && <StatusPill status={student.status} />}
          </div>
        </div>
      )}>
      {content}
    </PortalLayout>
  );
}

/** Pages read the selected child from here. */
export function useSelectedStudent() {
  return useOutletContext();
}
