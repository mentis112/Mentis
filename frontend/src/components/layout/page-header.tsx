export function PageHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div className="mb-7 flex flex-col gap-3 border-b border-border/55 pb-5 sm:flex-row sm:items-end sm:justify-between">
      <div className="space-y-2">
        <div className="h-1.5 w-14 rounded-full bg-primary/80" />
        <h2 className="text-2xl font-extrabold sm:text-3xl">{title}</h2>
        <p className="max-w-3xl text-sm leading-7 text-foreground/65">{subtitle}</p>
      </div>
    </div>
  );
}
