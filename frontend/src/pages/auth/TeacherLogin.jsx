import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { Clock, Eye, EyeOff, Smartphone } from "lucide-react";
import AuthShell, { CodeInput, StepDots } from "./AuthShell";
import { Button, Field, Input, Spinner } from "../../components/ui";
import { authApi } from "../../services/endpoints";
import { errorMessage } from "../../services/api";
import { useAuth } from "../../context/AuthContext";
import { fmtDate } from "../../utils/format";

const schema = z.object({
  identifier: z.string().trim().min(3, "Enter your Teacher ID or e-mail"),
  password: z.string().min(1, "Enter your password"),
});

const SESSION_TEXT = {
  morning: "Morning session – valid until the lunch break",
  afternoon: "Afternoon session – valid until school closing time",
  extended: "Outside school hours – short demo session",
};

export default function TeacherLogin() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [challenge, setChallenge] = useState(null);
  const [qr, setQr] = useState(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [showPw, setShowPw] = useState(false);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(schema) });

  useEffect(() => {
    if (challenge?.next_step !== "enroll" || qr) return;
    authApi.teacherTotpSetup(challenge.challenge_token).then((d) => setQr(d)).catch((e) => {
      toast.error(errorMessage(e));
      setChallenge(null);
    });
  }, [challenge, qr]);

  if (user?.role === "teacher") return <Navigate to="/teacher" replace />;

  const onPassword = async (values) => {
    try {
      const data = await authApi.teacherLogin(values);
      setQr(null);
      setCode("");
      setChallenge(data);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const onVerify = async (e) => {
    e.preventDefault();
    setBusy(true);
    try {
      await authApi.teacherTotpVerify({ challenge_token: challenge.challenge_token, code });
      await refresh();
      toast.success("Signed in.");
      navigate("/teacher", { replace: true });
    } catch (err) {
      toast.error(errorMessage(err));
      setCode("");
      if (err.response?.data?.code === "challenge_expired") setChallenge(null);
    } finally {
      setBusy(false);
    }
  };

  const enrolling = challenge?.next_step === "enroll";
  return (
    <AuthShell portal="Teacher Portal"
      title={!challenge ? "Sign in" : enrolling ? "Set up Google Authenticator" : "Two-step verification"}
      subtitle={!challenge ? "Enter your Teacher ID (or school e-mail) and password." : `Hello ${challenge.teacher_name}.`}
      aside={{ title: "Attendance that follows the timetable.", text: "Mark period-wise attendance, review substitute submissions and leave requests, and download salary slips." }}>
      <StepDots step={challenge ? 2 : 1} />
      {!challenge ? (
        <form onSubmit={handleSubmit(onPassword)} className="space-y-5" noValidate>
          <Field label="Teacher ID or e-mail" error={errors.identifier?.message} required>
            <Input autoFocus autoComplete="username" placeholder="e.g. T1001" {...register("identifier")} />
          </Field>
          <Field label="Password" error={errors.password?.message} required>
            <div className="relative">
              <Input type={showPw ? "text" : "password"} autoComplete="current-password" className="pr-11" {...register("password")} />
              <button type="button" onClick={() => setShowPw((s) => !s)} className="absolute inset-y-0 right-0 px-3 text-muted hover:text-brand-700" aria-label={showPw ? "Hide password" : "Show password"}>
                {showPw ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
              </button>
            </div>
          </Field>
          <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>Continue</Button>
        </form>
      ) : (
        <form onSubmit={onVerify} className="space-y-5">
          <div className="flex items-start gap-2.5 rounded-xl bg-brand-50 px-3.5 py-3 text-sm text-brand-900">
            <Clock className="mt-0.5 size-4 shrink-0 text-brand-600" />
            <span>{SESSION_TEXT[challenge.session_type]} ({fmtDate(challenge.session_expires_at, "hh:mm a")}). You will need to sign in again after it ends.</span>
          </div>
          {enrolling && (
            <div className="rounded-xl border border-line p-4">
              <ol className="list-decimal space-y-1 pl-5 text-sm text-ink-soft">
                <li>Open <b>Google Authenticator</b> on your phone.</li>
                <li>Tap <b>+</b> → <b>Scan a QR code</b> and scan the code below.</li>
                <li>Enter the 6-digit code shown in the app.</li>
              </ol>
              <div className="mt-4 grid place-items-center">
                {qr ? <img src={qr.qr_code} alt="Authenticator enrolment QR code" className="size-52 rounded-lg ring-1 ring-line" /> : <Spinner label="Preparing QR code…" />}
              </div>
              <p className="mt-2 text-center text-xs text-muted">Account: {qr?.issuer} · {qr?.account_label}</p>
            </div>
          )}
          {!enrolling && (
            <p className="flex items-center gap-2 text-sm text-ink-soft"><Smartphone className="size-4 text-brand-600" /> Enter the current code from Google Authenticator.</p>
          )}
          <CodeInput value={code} onChange={setCode} autoFocus={!enrolling} />
          <Button type="submit" size="lg" className="w-full" loading={busy} disabled={code.length !== 6}>
            {enrolling ? "Confirm and sign in" : "Verify and sign in"}
          </Button>
          <button type="button" onClick={() => setChallenge(null)} className="w-full text-center text-sm font-medium text-brand-700 hover:underline">Start again</button>
        </form>
      )}
    </AuthShell>
  );
}
