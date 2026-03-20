export function DetailJson({ data }: { data: unknown }) {
  return (
    <pre className="overflow-auto rounded-3xl bg-slate-950 p-5 text-xs text-slate-100">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}
