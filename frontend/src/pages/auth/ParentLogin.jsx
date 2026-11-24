import { useEffect, useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import toast from "react-hot-toast";
import { Eye, MessageSquareText, RotateCcw, ShieldCheck } from "lucide-react";
import AuthShell, { CodeInput, StepDots } from "./AuthShell";
import { Button, Field, Input } from "../../components/ui";
import { authApi } from "../../services/endpoints";
import { errorMessage } from "../../services/api";
import { useAuth } from "../../context/AuthContext";

const schema = z.object({
  identifier: z.string().trim().min(5, "Enter your registered mobile number or e-mail")
    .refine((v) => (v.includes("@") ? /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(v) : [10, 12].includes(v.replace(/\D/g, "").length)),
      "Enter a valid 10-digit mobile number or e-mail address"),
  roll_number: z.string().trim().min(1, "Enter your child's roll number").regex(/^[A-Za-z0-9\-/]+$/, "Letters and digits only"),
});

function useCountdown(seconds) {
  const [left, setLeft] = useState(seconds);
  useEffect(() => setLeft(seconds), [seconds]);
  useEffect(() => {
    if (left <= 0) return undefined;
    const t = setTimeout(() => setLeft((s) => s - 1), 1000);
    return () => clearTimeout(t);
  }, [left]);
  return [left, setLeft];
}

const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export default function ParentLogin() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const [otp, setOtp] = useState(null);
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [inbox, setInbox] = useState(null);
  const [expiresIn, setExpiresIn] = useCountdown(0);
  const [resendIn, setResendIn] = useCountdown(0);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(schema) });

  if (user?.role === "parent") return <Navigate to="/parent" replace />;

  const startOtp = (data) => {
    setOtp(data);
    setCode("");
    setInbox(null);
    setExpiresIn(data.expires_in);
    setResendIn(data.resend_after);
  };

  const onIdentify = async (values) => {
    try {
      startOtp(await authApi.parentRequestOtp(values));
      toast.success("Verification code sent.");
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const onVerify = async (e) => {
    e.preventDefault();
    if (code.length !== 6) return toast.error("Enter the 6-digit code.");
    setBusy(true);
    try {
      await authApi.parentVerifyOtp({ request_id: otp.request_id, code });
      await refresh();
      toast.success("Welcome!");
      navigate("/parent", { replace: true });
    } catch (err) {
      toast.error(errorMessage(err));
      setCode("");
      if ([429].includes(err.response?.status) || ["otp_invalid", "otp_expired"].includes(err.response?.data?.code)) setOtp(null);
    } finally {
      setBusy(false);
    }
  };

  const onResend = async () => {
    try {
      startOtp(await authApi.parentResendOtp(otp.request_id));
      toast.success("A new code has been sent.");
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  const showInbox = async () => {
    try {
      setInbox(await authApi.parentDemoInbox(otp.request_id));
    } catch (err) {
      toast.error(errorMessage(err));
    }
  };

  return (
    <AuthShell portal="Parent Portal" title={otp ? "Enter verification code" : "Sign in"}
      subtitle={otp ? `We sent a 6-digit code to ${otp.destination}.` : "Use the mobile number or e-mail registered with the school, and your child's roll number."}
      aside={{ title: "Stay close to your child's school day.", text: "Attendance for every period, leave requests, fee details and receipts – in one secure place." }}>
      <StepDots step={otp ? 2 : 1} />
      {!otp ? (
        <form onSubmit={handleSubmit(onIdentify)} className="space-y-5" noValidate>
          <Field label="Registered mobile number or e-mail" error={errors.identifier?.message} required>
            <Input autoFocus autoComplete="username" placeholder="e.g. 98400 11001 or name@example.com" {...register("identifier")} />
          </Field>
          <Field label="Student roll number" error={errors.roll_number?.message} hint="Printed on your child's ID card, e.g. 6A01" required>
            <Input placeholder="e.g. 6A01" className="uppercase" {...register("roll_number")} />
          </Field>
          <Button type="submit" size="lg" className="w-full" loading={isSubmitting}>Send verification code</Button>
          <p className="flex items-start gap-2 text-xs text-muted"><ShieldCheck className="size-4 shrink-0 text-brand-500" />
            For your child's privacy we never confirm which details are registered.</p>
        </form>
      ) : (
        <form onSubmit={onVerify} className="space-y-5">
          <CodeInput value={code} onChange={setCode} />
          <div className="flex items-center justify-between text-sm">
            <span className={expiresIn > 0 ? "text-ink-soft" : "text-[#a8361f]"}>
              {expiresIn > 0 ? <>Code expires in <b className="num">{mmss(expiresIn)}</b></> : "Code expired – request a new one"}
            </span>
            <span className="text-muted">{otp.attempts_remaining} attempts</span>
          </div>
          <Button type="submit" size="lg" className="w-full" loading={busy} disabled={code.length !== 6}>Verify and sign in</Button>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button type="button" variant="ghost" size="sm" icon={RotateCcw} disabled={resendIn > 0 || otp.resends_remaining <= 0} onClick={onResend}>
              {resendIn > 0 ? `Resend in ${resendIn}s` : "Resend code"}
            </Button>
            <button type="button" onClick={() => setOtp(null)} className="text-sm font-medium text-brand-700 hover:underline">Use different details</button>
          </div>

          {otp.demo_inbox_enabled && (
            <div className="rounded-xl border border-dashed border-brand-300 bg-brand-50 p-4">
              <div className="flex items-center justify-between gap-2">
                <p className="flex items-center gap-2 text-sm font-semibold text-brand-800"><MessageSquareText className="size-4" /> Demo message inbox</p>
                <span className="rounded bg-brand-700 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white">Demo only</span>
              </div>
              <p className="mt-1 text-xs text-muted">No real SMS/e-mail is sent in this local demo. The code is also printed in the backend console.</p>
              {inbox ? (
                <div className="mt-3 rounded-lg bg-white p-3 text-sm ring-1 ring-line">
                  <p className="text-xs text-muted">To {inbox.destination} · {inbox.channel.toUpperCase()}</p>
                  <p className="mt-1">Your Sri Vidya Mandir parent portal code is <b className="num font-mono text-base tracking-widest">{inbox.code}</b>. Do not share it.</p>
                </div>
              ) : (
                <Button type="button" size="sm" variant="secondary" icon={Eye} className="mt-3" onClick={showInbox}>Show simulated message</Button>
              )}
            </div>
          )}
        </form>
      )}
    </AuthShell>
  );
}
