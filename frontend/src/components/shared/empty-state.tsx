import { ReactNode } from "react";

import { Card } from "@/components/shared/card";

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <Card className="p-8 text-center">
      <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-xl border border-border/70 bg-muted/70">
        {icon || <span className="h-2.5 w-2.5 rounded-full bg-primary" />}
      </div>
      <div className="space-y-3">
        <h3 className="text-lg font-bold">{title}</h3>
        <p className="mx-auto max-w-lg text-sm leading-7 text-foreground/65">{description}</p>
        {action ? <div className="pt-2">{action}</div> : null}
      </div>
    </Card>
  );
}
