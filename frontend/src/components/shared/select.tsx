import { forwardRef, SelectHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const Select = forwardRef<HTMLSelectElement, SelectHTMLAttributes<HTMLSelectElement>>(
  ({ className, ...props }, ref) => (
    <select
      ref={ref}
      className={cn(
        "h-11 w-full rounded-xl border border-border/75 bg-card/70 px-3 text-sm font-medium outline-none transition duration-200 hover:border-foreground/25 focus:border-primary focus:bg-card focus:ring-4 focus:ring-primary/10",
        className,
      )}
      {...props}
    />
  ),
);

Select.displayName = "Select";
