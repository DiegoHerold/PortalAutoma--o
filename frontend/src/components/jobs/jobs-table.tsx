import type { Job } from "@/types/job";

type JobsTableProps = {
  jobs?: Job[];
};

export function JobsTable({ jobs = [] }: JobsTableProps) {
  return (
    <div className="overflow-hidden rounded-3xl border border-slate-200 bg-white/80 shadow-sm">
      <table className="min-w-full text-sm">
        <thead className="bg-slate-50 text-left text-slate-500">
          <tr>
            <th className="px-4 py-3">ID</th>
            <th className="px-4 py-3">Automacao</th>
            <th className="px-4 py-3">Status</th>
            <th className="px-4 py-3">Prioridade</th>
          </tr>
        </thead>
        <tbody>
          {jobs.length === 0 ? (
            <tr>
              <td className="px-4 py-6 text-slate-500" colSpan={4}>
                Nenhum job carregado ainda.
              </td>
            </tr>
          ) : (
            jobs.map((job) => (
              <tr key={job.id} className="border-t border-slate-100">
                <td className="px-4 py-3">{job.id}</td>
                <td className="px-4 py-3">{job.automation_id}</td>
                <td className="px-4 py-3">{job.status}</td>
                <td className="px-4 py-3">{job.priority}</td>
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
