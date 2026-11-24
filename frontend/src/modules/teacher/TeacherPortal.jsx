import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BadgeIndianRupee, CalendarCheck, Contact, IdCard, UserCog, UsersRound } from "lucide-react";
import PortalLayout from "../../layouts/PortalLayout";
import { useAuth } from "../../context/AuthContext";
import { teacherApi } from "../../services/endpoints";
import { cx } from "../../components/ui";

const SESSION_LABEL = { morning: "Morning session", afternoon: "Afternoon session", extended: "Demo session (off-hours)" };

function SessionChip({ session, onExpire }) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const left = Math.max(0, Math.floor((new Date(session.expires_at).getTime() - now) / 1000));
  useEffect(() => {
    if (left === 0) onExpire();
  }, [left, onExpire]);
  const h = Math.floor(left / 3600), m = Math.floor((left % 3600) / 60), s = left % 60;
  const text = h ? `${h}h ${m}m` : `${m}:${String(s).padStart(2, "0")}`;
  const warn = left < 300;
  return (
    <div className={cx("hidden items-center gap-2 rounded-full border px-3 py-1.5 text-xs sm:flex", warn ? "border-[#ecd3a8] bg-[#fbf1e2] text-[#8f5f14]" : "border-line bg-brand-50 text-brand-800")}
      title={`Ends at ${new Date(session.expires_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })} – sign in again for the next session`}>
      <span className={cx("size-2 rounded-full", warn ? "bg-[#c98a2b]" : "bg-[#0e8a6a]")} />
      <span className="font-medium">{SESSION_LABEL[session.type] || "Session"}</span>
      <span className="num">· ends in {text}</span>
    </div>
  );
}

export default function TeacherPortal() {
  const { user, refresh } = useAuth();
  const profile = useQuery({ queryKey: ["teacher", "profile"], queryFn: teacherApi.profile, refetchInterval: 120_000 });
  const p = profile.data;
  const nav = [
    { to: "/teacher/profile", label: "Teacher Details", icon: IdCard },
    { to: "/teacher/attendance", label: "Attendance", icon: CalendarCheck, badge: p?.pending_leave_requests || null },
    { to: "/teacher/substitute", label: "Substitute Approval", icon: UsersRound, badge: p?.pending_approvals || null },
    { to: "/teacher/manage-students", label: "Add & Remove Students", icon: UserCog },
    { to: "/teacher/students", label: "Student Details", icon: Contact },
    { to: "/teacher/salary", label: "Salary", icon: BadgeIndianRupee },
  ];
  return (
    <PortalLayout portalLabel="Teacher Portal" nav={nav} outletContext={{ profile: p }}
      context={<p className="truncate text-sm text-ink-soft"><span className="font-semibold text-ink">{user?.name}</span>{p && <span className="hidden sm:inline"> · {p.designation}</span>}</p>}
      headerExtra={user?.session && <SessionChip session={user.session} onExpire={refresh} />} />
  );
}
