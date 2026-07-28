export function WorkerStatusBadge({ status }: { status: string }) {
  return <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium">{status}</span>;
}
