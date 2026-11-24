import { useState } from "react";
import { useOutletContext } from "react-router-dom";
import { BarChart3, ClipboardCheck, ClipboardList } from "lucide-react";
import { PageHeader, Tabs } from "../../components/ui";
import MarkAttendance from "./MarkAttendance";
import LeaveApprovals from "./LeaveApprovals";
import AttendanceReports from "./AttendanceReports";

export default function TeacherAttendance() {
  const { profile } = useOutletContext() || {};
  const [tab, setTab] = useState("mark");
  return (
    <>
      <PageHeader title="Attendance" description="Mark period-wise attendance from your timetable, decide leave requests and review attendance analytics." />
      <div className="mb-6">
        <Tabs value={tab} onChange={setTab} tabs={[
          { value: "mark", label: "Mark attendance", icon: ClipboardCheck },
          { value: "leave", label: "Leave requests", icon: ClipboardList, count: profile?.pending_leave_requests },
          { value: "reports", label: "Reports & analytics", icon: BarChart3 },
        ]} />
      </div>
      {tab === "mark" && <MarkAttendance />}
      {tab === "leave" && <LeaveApprovals />}
      {tab === "reports" && <AttendanceReports />}
    </>
  );
}
