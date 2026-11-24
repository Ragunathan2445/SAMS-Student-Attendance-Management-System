import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { AlertTriangle, BadgeCheck, CalendarClock, Download, IndianRupee, Receipt, Wallet } from "lucide-react";
import { useSelectedStudent } from "./ParentPortal";
import { Badge, Button, Card, EmptyState, PageHeader, QueryState, StatTile, StatusPill, TableWrap, Tabs } from "../../components/ui";
import { parentApi } from "../../services/endpoints";
import { errorMessage, safeDownload } from "../../services/api";
import { fmtDate, formatINR, isPositive } from "../../utils/format";

export function ReceiptButton({ payment }) {
  const [busy, setBusy] = useState(false);
  if (!payment.receipt_available) return <span className="text-xs text-muted">No receipt</span>;
  return (
    <Button size="sm" variant="secondary" icon={Download} loading={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await safeDownload(`/parent/payments/${payment.id}/receipt`, `receipt-${payment.receipt_number}.pdf`);
        } catch (e) {
          toast.error(errorMessage(e));
        } finally {
          setBusy(false);
        }
      }}>PDF</Button>
  );
}

export function PaymentsTable({ payments }) {
  if (!payments.length) return <EmptyState icon={Receipt} title="No payments in this period" />;
  return (
    <TableWrap>
      <table className="table-base">
        <thead><tr><th>Date</th><th>Transaction ref.</th><th>Fee category</th><th className="text-right">Amount</th><th>Method</th><th>Status</th><th>Receipt</th><th /></tr></thead>
        <tbody>
          {payments.map((p) => (
            <tr key={p.id}>
              <td className="whitespace-nowrap">{fmtDate(p.payment_date)}</td>
              <td className="num font-mono text-xs">{p.transaction_ref}</td>
              <td><p>{p.category_label}</p><p className="text-xs text-muted">{p.description}</p></td>
              <td className="num whitespace-nowrap text-right font-semibold">{formatINR(p.amount)}</td>
              <td>{p.method_label}</td>
              <td><StatusPill status={p.status} /></td>
              <td className="num whitespace-nowrap font-mono text-xs">{p.receipt_number || "—"}</td>
              <td><ReceiptButton payment={p} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

export function LedgerTable({ entries }) {
  if (!entries.length) return <EmptyState title="No ledger entries" />;
  const TYPE = { opening: "neutral", charge: "warning", payment: "success", adjustment: "pending" };
  return (
    <TableWrap>
      <table className="table-base">
        <thead><tr><th>#</th><th>Date</th><th>Entry</th><th>Description</th><th className="text-right">Charge (+)</th><th className="text-right">Paid / credit (−)</th><th className="text-right">Balance</th></tr></thead>
        <tbody>
          {entries.map((e) => (
            <tr key={e.sequence}>
              <td className="num text-muted">{e.sequence}</td>
              <td className="whitespace-nowrap">{fmtDate(e.entry_date)}</td>
              <td><Badge tone={TYPE[e.entry_type]}>{e.entry_type}</Badge></td>
              <td>{e.description}</td>
              <td className="num whitespace-nowrap text-right">{isPositive(e.debit) ? formatINR(e.debit) : "—"}</td>
              <td className="num whitespace-nowrap text-right text-[#0a6a51]">{isPositive(e.credit) ? formatINR(e.credit) : "—"}</td>
              <td className="num whitespace-nowrap text-right font-semibold">{formatINR(e.balance_after)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </TableWrap>
  );
}

function FeeDetails({ fees }) {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatTile label="Total fee" value={formatINR(fees.total_fee)} sub={isPositive(fees.opening_balance) ? `+ ${formatINR(fees.opening_balance)} carried forward` : `Academic year ${fees.academic_year}`} icon={IndianRupee} accent="#6f4529" />
        <StatTile label="Amount paid" value={formatINR(fees.amount_paid)} sub={fees.total_adjustments !== "0.00" ? `Concessions ${formatINR(fees.total_adjustments)}` : "Successful payments"} icon={BadgeCheck} accent="var(--color-st-present)" />
        <StatTile label="Pending (overdue)" value={formatINR(fees.pending_amount)} sub="Due date has passed" icon={AlertTriangle} accent="var(--color-st-absent)" />
        <StatTile label="Balance amount" value={formatINR(fees.balance_amount)} sub={fees.next_due ? `Next due ${fmtDate(fees.next_due.due_date)}` : "Including future instalments"} icon={Wallet} accent="#c98a2b" />
      </div>
      <Card title="Fee categories" subtitle={fees.ledger_reconciled ? "Balance reconciled with the transaction ledger" : "Ledger check pending"}>
        <TableWrap>
          <table className="table-base">
            <thead><tr><th>Category</th><th className="text-right">Charged</th><th className="text-right">Adjustments</th><th className="text-right">Paid</th><th className="text-right">Overdue</th><th className="text-right">Balance</th></tr></thead>
            <tbody>
              {fees.categories.map((c) => (
                <tr key={c.category}>
                  <td className="font-medium">{c.category_label}</td>
                  <td className="num text-right">{formatINR(c.charged)}</td>
                  <td className="num text-right">{c.adjustments === "0.00" ? "—" : formatINR(c.adjustments)}</td>
                  <td className="num text-right">{formatINR(c.paid)}</td>
                  <td className="num text-right">{isPositive(c.overdue) ? <span className="text-[#a3341f]">{formatINR(c.overdue)}</span> : "—"}</td>
                  <td className="num text-right font-semibold">{formatINR(c.balance)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Card>
      <Card title="Fee items & due dates">
        <TableWrap>
          <table className="table-base">
            <thead><tr><th>Item</th><th>Due date</th><th className="text-right">Amount</th><th className="text-right">Paid</th><th className="text-right">Balance</th><th>Status</th></tr></thead>
            <tbody>
              {fees.items.map((i) => (
                <tr key={i.id}>
                  <td><p className="font-medium">{i.description}</p><p className="text-xs text-muted">{i.category_label}</p></td>
                  <td className="whitespace-nowrap"><span className="inline-flex items-center gap-1.5"><CalendarClock className="size-3.5 text-brand-400" />{fmtDate(i.due_date)}</span></td>
                  <td className="num text-right">{formatINR(i.amount)}{i.adjustments !== "0.00" && <p className="text-xs text-muted">{formatINR(i.adjustments)} adj.</p>}</td>
                  <td className="num text-right">{formatINR(i.paid)}</td>
                  <td className="num text-right font-semibold">{formatINR(i.balance)}</td>
                  <td><StatusPill status={i.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </TableWrap>
      </Card>
    </div>
  );
}

export default function Payments() {
  const { student } = useSelectedStudent();
  const [tab, setTab] = useState("fees");
  const fees = useQuery({ queryKey: ["parent", "fees", student.id], queryFn: () => parentApi.fees(student.id) });
  const payments = useQuery({ queryKey: ["parent", "payments", student.id], queryFn: () => parentApi.payments(student.id), enabled: tab === "payments" });
  const ledger = useQuery({ queryKey: ["parent", "ledger", student.id], queryFn: () => parentApi.balanceHistory(student.id), enabled: tab === "balance" });

  return (
    <>
      <PageHeader title="Payment & Receipts" description={`Fee details for ${student.full_name}. Fee amounts are set by the school office.`}
        actions={<Badge tone="warning">Demo / sample financial records</Badge>} />
      <div className="mb-6"><Tabs value={tab} onChange={setTab} tabs={[{ value: "fees", label: "Fee details" }, { value: "payments", label: "Payment history" }, { value: "balance", label: "Balance history" }]} /></div>
      {tab === "fees" && <QueryState query={fees}>{fees.data && <FeeDetails fees={fees.data} />}</QueryState>}
      {tab === "payments" && <Card title="Payment history" subtitle="Download the PDF receipt for any successful payment"><QueryState query={payments}>{payments.data && <PaymentsTable payments={payments.data.payments} />}</QueryState></Card>}
      {tab === "balance" && (
        <Card title="Balance history" subtitle={ledger.data ? `Every charge, adjustment and payment in order · closing balance ${formatINR(ledger.data.closing_balance)}` : null}
          action={ledger.data?.chain_consistent && <Badge tone="success">Ledger verified</Badge>}>
          <QueryState query={ledger}>{ledger.data && <LedgerTable entries={ledger.data.entries} />}</QueryState>
        </Card>
      )}
    </>
  );
}
