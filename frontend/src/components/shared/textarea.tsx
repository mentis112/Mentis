import { forwardRef, TextareaHTMLAttributes } from "react";

import { cn } from "@/lib/cn";

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea
    ref={ref}
    className={cn(
      "min-h-28 w-full rounded-xl border border-border/75 bg-card/70 px-3 py-2 text-sm font-medium outline-none transition duration-200 placeholder:text-foreground/35 hover:border-foreground/25 focus:border-primary focus:bg-card focus:ring-4 focus:ring-primary/10",
      className,
    )}
    {...props}
  />
));

Textarea.displayName = "Textarea";
