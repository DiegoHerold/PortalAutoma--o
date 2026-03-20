type PageTitleProps = {
  eyebrow?: string;
  title: string;
  description: string;
};

export function PageTitle({ eyebrow, title, description }: PageTitleProps) {
  return (
    <div className="space-y-2">
      {eyebrow ? <p className="text-sm font-semibold uppercase tracking-[0.24em] text-accent">{eyebrow}</p> : null}
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      <p className="max-w-3xl text-sm text-slate-600">{description}</p>
    </div>
  );
}
