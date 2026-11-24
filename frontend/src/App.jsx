import { Navigate, Route, Routes } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import LandingPage from "./pages/LandingPage";
import NotFound from "./pages/NotFound";
import ParentLogin from "./pages/auth/ParentLogin";
import TeacherLogin from "./pages/auth/TeacherLogin";
import ParentPortal from "./modules/parent/ParentPortal";
import StudentDetails from "./modules/parent/StudentDetails";
import ParentAttendance from "./modules/parent/Attendance";
import LeaveInformation from "./modules/parent/Leave";
import Payments from "./modules/parent/Payments";
import History from "./modules/parent/History";
import TeacherPortal from "./modules/teacher/TeacherPortal";
import TeacherDetails from "./modules/teacher/TeacherDetails";
import TeacherAttendance from "./modules/teacher/Attendance";
import SubstituteAttendance from "./modules/teacher/Substitute";
import ManageStudents from "./modules/teacher/ManageStudents";
import StudentDirectory from "./modules/teacher/StudentDirectory";
import Salary from "./modules/teacher/Salary";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/parent/login" element={<ParentLogin />} />
      <Route path="/teacher/login" element={<TeacherLogin />} />

      <Route path="/parent" element={<ProtectedRoute role="parent"><ParentPortal /></ProtectedRoute>}>
        <Route index element={<Navigate to="student" replace />} />
        <Route path="student" element={<StudentDetails />} />
        <Route path="attendance" element={<ParentAttendance />} />
        <Route path="leave" element={<LeaveInformation />} />
        <Route path="payments" element={<Payments />} />
        <Route path="history" element={<History />} />
      </Route>

      <Route path="/teacher" element={<ProtectedRoute role="teacher"><TeacherPortal /></ProtectedRoute>}>
        <Route index element={<Navigate to="profile" replace />} />
        <Route path="profile" element={<TeacherDetails />} />
        <Route path="attendance" element={<TeacherAttendance />} />
        <Route path="substitute" element={<SubstituteAttendance />} />
        <Route path="manage-students" element={<ManageStudents />} />
        <Route path="students" element={<StudentDirectory />} />
        <Route path="salary" element={<Salary />} />
      </Route>

      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
