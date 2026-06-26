import { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Badge({ className, ...props }: HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border border-border/70 bg-muted/70 px-2.5 py-1 text-xs font-bold text-foreground/75 shadow-sm",
        className,
      )}
      {...props}
    />
  );
}
