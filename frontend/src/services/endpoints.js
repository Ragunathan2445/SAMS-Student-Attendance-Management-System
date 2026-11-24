import { api } from "./api";

const data = (p) => p.then((r) => r.data);
const qs = (params = {}) => {
  const s = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") s.set(k, v);
  });
  const str = s.toString();
  return str ? `?${str}` : "";
};

export const publicApi = {
  school: () => data(api.get("/public/school")),
};

export const authApi = {
  me: () => data(api.get("/auth/me")),
  logout: () => data(api.post("/auth/logout")),
  parentRequestOtp: (body) => data(api.post("/auth/parent/request-otp", body)),
  parentResendOtp: (request_id) => data(api.post("/auth/parent/resend-otp", { request_id })),
  parentVerifyOtp: (body) => data(api.post("/auth/parent/verify-otp", body)),
  parentDemoInbox: (requestId) => data(api.get(`/auth/parent/demo-inbox/${requestId}`)),
  teacherLogin: (body) => data(api.post("/auth/teacher/login", body)),
  teacherTotpSetup: (challenge_token) => data(api.post("/auth/teacher/totp/setup", { challenge_token })),
  teacherTotpVerify: (body) => data(api.post("/auth/teacher/totp/verify", body)),
};

export const parentApi = {
  students: () => data(api.get("/parent/students")),
  profile: (id) => data(api.get(`/parent/students/${id}/profile`)),
  overview: (id) => data(api.get(`/parent/students/${id}/attendance/overview`)),
  daily: (id, date) => data(api.get(`/parent/students/${id}/attendance/daily${qs({ date })}`)),
  weekly: (id, date) => data(api.get(`/parent/students/${id}/attendance/weekly${qs({ date })}`)),
  monthly: (id, year, month) => data(api.get(`/parent/students/${id}/attendance/monthly${qs({ year, month })}`)),
  yearly: (id) => data(api.get(`/parent/students/${id}/attendance/yearly`)),
  attendanceHistory: (id, from, to) => data(api.get(`/parent/students/${id}/attendance/history${qs({ from, to })}`)),
  academicRecords: (id) => data(api.get(`/parent/students/${id}/academic-records`)),
  leaveRequests: (params) => data(api.get(`/parent/leave-requests${qs(params)}`)),
  createLeave: (formData) => data(api.post("/parent/leave-requests", formData)),
  fees: (id) => data(api.get(`/parent/students/${id}/fees`)),
  payments: (id, from, to) => data(api.get(`/parent/students/${id}/payments${qs({ from, to })}`)),
  balanceHistory: (id, from, to) => data(api.get(`/parent/students/${id}/balance-history${qs({ from, to })}`)),
};

export const teacherApi = {
  profile: () => data(api.get("/teacher/profile")),
  sections: () => data(api.get("/teacher/sections")),
  slots: (date) => data(api.get(`/teacher/attendance/slots${qs({ date })}`)),
  sheet: (params) => data(api.get(`/teacher/attendance/sheet${qs(params)}`)),
  submitAttendance: (body) => data(api.post("/teacher/attendance", body)),
  correctAttendance: (id, body) => data(api.patch(`/teacher/attendance/${id}`, body)),
  leaveRequests: (status) => data(api.get(`/teacher/leave-requests${qs({ status })}`)),
  decideLeave: (id, body) => data(api.post(`/teacher/leave-requests/${id}/decision`, body)),
  classReport: (params) => data(api.get(`/teacher/analytics/class${qs(params)}`)),
  monthly: (section_id) => data(api.get(`/teacher/analytics/monthly${qs({ section_id })}`)),
  studentReport: (id) => data(api.get(`/teacher/analytics/students/${id}`)),
  subAssignments: () => data(api.get("/teacher/substitute/assignments")),
  subSheet: (id) => data(api.get(`/teacher/substitute/assignments/${id}/sheet`)),
  subSubmit: (id, records) => data(api.post(`/teacher/substitute/assignments/${id}/submissions`, { records })),
  subMine: () => data(api.get("/teacher/substitute/submissions/mine")),
  subApprovals: (status) => data(api.get(`/teacher/substitute/approvals${qs({ status })}`)),
  subDetail: (id) => data(api.get(`/teacher/substitute/submissions/${id}`)),
  subApprove: (id) => data(api.post(`/teacher/substitute/submissions/${id}/approve`)),
  subReject: (id, reason) => data(api.post(`/teacher/substitute/submissions/${id}/reject`, { reason })),
  manageList: (params) => data(api.get(`/teacher/manage/students${qs(params)}`)),
  createStudent: (fd) => data(api.post("/teacher/manage/students", fd)),
  updateStudent: (id, fd) => data(api.put(`/teacher/manage/students/${id}`, fd)),
  deactivate: (id, body) => data(api.post(`/teacher/manage/students/${id}/deactivate`, body)),
  reactivate: (id, body) => data(api.post(`/teacher/manage/students/${id}/reactivate`, body)),
  studentHistory: (id) => data(api.get(`/teacher/manage/students/${id}/history`)),
  directory: (params) => data(api.get(`/teacher/students/directory${qs(params)}`)),
  salaries: () => data(api.get("/teacher/salary")),
  salary: (id) => data(api.get(`/teacher/salary/${id}`)),
};

export { qs };
