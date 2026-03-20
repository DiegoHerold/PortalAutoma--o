export function PriorityBadge({ priority }: { priority: string }) {
  return <span className="rounded-full bg-mist px-3 py-1 text-xs font-medium uppercase">{priority}</span>;
}
