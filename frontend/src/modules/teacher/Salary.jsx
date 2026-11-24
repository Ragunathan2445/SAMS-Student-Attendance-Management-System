import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { Download, IndianRupee, MinusCircle, Wallet } from "lucide-react";
import { Badge, Button, Card, PageHeader, QueryState, StatTile, StatusPill, TableWrap, cx } from "../../components/ui";
import { teacherApi } from "../../services/endpoints";
import { errorMessage, safeDownload } from "../../services/api";
import { fmtDate, formatINR, isPositive } from "../../utils/format";

function SlipButton({ salary, size = "sm", variant = "secondary" }) {
  const [busy, setBusy] = useState(false);
  return (
    <Button size={size} variant={variant} icon={Download} loading={busy}
      onClick={async (e) => {
        e.stopPropagation();
        setBusy(true);
        try { await safeDownload(`/teacher/salary/${salary.id}/slip`, `salary-slip-${salary.salary_month.slice(0, 7)}.pdf`); }
        catch (err) { toast.error(errorMessage(err)); }
        finally { setBusy(false); }
      }}>Salary slip</Button>
  );
}

function SalaryDetail({ id }) {
  const q = useQuery({ queryKey: ["teacher", "salary", id], queryFn: () => teacherApi.salary(id), enabled: Boolean(id) });
  const s = q.data;
  return (
    <Card title={s ? `Salary – ${s.month_label}` : "Salary details"} action={s && <SlipButton salary={s} size="md" variant="primary" />}>
      <QueryState query={q}>
        {s && (
          <div className="space-y-5">
            <div className="flex flex-wrap gap-2 text-sm">
              <StatusPill status={s.status} label={s.status_label} />
              <Badge>{s.teacher_name} · {s.teacher_code}</Badge>
              <Badge>{s.days_present}/{s.working_days} days present</Badge>
              {s.payment_date && <Badge tone="success">Paid on {fmtDate(s.payment_date)}</Badge>}
            </div>
            <div className="grid gap-5 md:grid-cols-2">
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Earnings</p>
                <dl className="divide-y divide-line rounded-xl border border-line text-sm">
                  <div className="flex justify-between px-3 py-2"><dt>Basic salary</dt><dd className="num">{formatINR(s.basic_salary)}</dd></div>
                  {s.allowance_breakdown.map((a) => <div key={a.label} className="flex justify-between px-3 py-2"><dt>{a.label}</dt><dd className="num">{formatINR(a.amount)}</dd></div>)}
                  <div className="flex justify-between bg-brand-50 px-3 py-2 font-semibold"><dt>Gross salary</dt><dd className="num">{formatINR(s.gross_salary)}</dd></div>
                </dl>
              </div>
              <div>
                <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted">Deductions (recorded separately)</p>
                <dl className="divide-y divide-line rounded-xl border border-line text-sm">
                  {s.deductions.map((d, i) => (
                    <div key={i} className={cx("flex justify-between gap-3 px-3 py-2", d.is_penalty && "bg-[#fdf6f4]")}>
                      <dt>{d.label}{d.is_penalty && <Badge tone="danger" className="ml-2">Penalty</Badge>}<p className="text-xs text-muted">{d.description}</p></dt>
                      <dd className="num whitespace-nowrap">{formatINR(d.amount)}</dd>
                    </div>
                  ))}
                  <div className="flex justify-between px-3 py-2 text-ink-soft"><dt>Penalty deductions</dt><dd className="num">{formatINR(s.penalty_deductions)}</dd></div>
                  <div className="flex justify-between bg-brand-50 px-3 py-2 font-semibold"><dt>Total deductions</dt><dd className="num">{formatINR(s.total_deductions)}</dd></div>
                </dl>
              </div>
            </div>
            <div className="flex items-center justify-between rounded-xl bg-brand-800 px-5 py-4 text-white">
              <span className="font-medium">Net salary</span><span className="num font-serif text-2xl font-semibold">{formatINR(s.net_salary)}</span>
            </div>
            {s.payments.map((p) => <p key={p.reference_number} className="text-xs text-muted">Bank transfer {p.reference_number} · {fmtDate(p.payment_date)} · {formatINR(p.amount)}</p>)}
          </div>
        )}
      </QueryState>
    </Card>
  );
}

export default function Salary() {
  const q = useQuery({ queryKey: ["teacher", "salaries"], queryFn: teacherApi.salaries });
  const list = q.data?.salaries || [];
  const [selected, setSelected] = useState(null);
  useEffect(() => { if (!selected && list.length) setSelected(list.find((s) => s.status === "paid")?.id || list[0].id); }, [list, selected]);
  const latest = list.find((s) => s.status === "paid");

  return (
    <>
      <PageHeader title="Salary" description="Salary details are provided by the school office and cannot be edited here." actions={<Badge tone="warning">Demo / sample salary data</Badge>} />
      <QueryState query={q}>
        <div className="space-y-6">
          {latest && (
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              <StatTile label="Last net salary" value={formatINR(latest.net_salary)} sub={latest.month_label} icon={Wallet} accent="#6f4529" />
              <StatTile label="Gross salary" value={formatINR(latest.gross_salary)} sub={`Allowances ${formatINR(latest.allowances)}`} icon={IndianRupee} accent="#a26f45" />
              <StatTile label="Deductions" value={formatINR(latest.total_deductions)} sub={isPositive(latest.penalty_deductions) ? `incl. penalties ${formatINR(latest.penalty_deductions)}` : "No penalties"} icon={MinusCircle} accent="var(--color-st-absent)" />
              <StatTile label="Payment status" value={latest.status_label} sub={fmtDate(latest.payment_date)} accent="var(--color-st-present)" />
            </div>
          )}
          <div className="grid gap-6 xl:grid-cols-[1fr_1fr]">
            <Card title="Salary history">
              <TableWrap>
                <table className="table-base">
                  <thead><tr><th>Month</th><th className="text-right">Gross</th><th className="text-right">Deductions</th><th className="text-right">Net</th><th>Status</th><th /></tr></thead>
                  <tbody>
                    {list.map((s) => (
                      <tr key={s.id} onClick={() => setSelected(s.id)} className={cx("cursor-pointer", selected === s.id && "[&>td]:bg-brand-50")}>
                        <td className="whitespace-nowrap font-medium">{s.month_label}</td>
                        <td className="num text-right">{formatINR(s.gross_salary)}</td>
                        <td className="num text-right">{formatINR(s.total_deductions)}{isPositive(s.penalty_deductions) && <span className="block text-xs text-[#a3341f]">penalty {formatINR(s.penalty_deductions)}</span>}</td>
                        <td className="num text-right font-semibold">{formatINR(s.net_salary)}</td>
                        <td><StatusPill status={s.status} label={s.status_label} /></td>
                        <td className="text-right"><SlipButton salary={s} /></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </TableWrap>
            </Card>
            {selected && <SalaryDetail id={selected} />}
          </div>
        </div>
      </QueryState>
    </>
  );
}
