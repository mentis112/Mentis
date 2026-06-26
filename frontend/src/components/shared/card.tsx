import { HTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "glass-panel rounded-2xl transition duration-200 hover:border-primary/20",
        className,
      )}
      {...props}
    />
  );
}
