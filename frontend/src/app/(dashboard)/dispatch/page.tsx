import { redirect } from "next/navigation";

type SearchParams = Promise<Record<string, string | string[] | undefined>>;

export default async function DispatchPage({ searchParams }: { searchParams: SearchParams }) {
  const params = normalizeSearchParams(await searchParams);
  params.set("status", "waiting");
  params.delete("limit");
  redirect(`/executions?${params.toString()}`);
}

function normalizeSearchParams(values: Record<string, string | string[] | undefined>): URLSearchParams {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => {
    if (Array.isArray(value)) value.forEach((item) => params.append(key, item));
    else if (value) params.set(key, value);
  });
  return params;
}
