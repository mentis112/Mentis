import { ButtonHTMLAttributes, forwardRef } from "react";

import { cn } from "@/lib/cn";

type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
}

const variants: Record<ButtonVariant, string> = {
  primary:
    "bg-primary text-white shadow-glow hover:-translate-y-0.5 hover:bg-primary/95 active:translate-y-0 dark:text-slate-950",
  secondary:
    "border border-border/70 bg-card/75 text-foreground shadow-sm hover:-translate-y-0.5 hover:border-primary/35 hover:bg-secondary/75 active:translate-y-0",
  ghost:
    "bg-transparent text-foreground/75 hover:bg-muted/80 hover:text-foreground",
  danger:
    "bg-danger text-white shadow-sm hover:-translate-y-0.5 hover:bg-danger/92 active:translate-y-0",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = "primary", ...props }, ref) => (
    <button
      ref={ref}
      className={cn(
        "inline-flex h-11 items-center justify-center gap-2 rounded-xl px-4 text-sm font-bold transition duration-200 focus:outline-none focus:ring-2 focus:ring-primary/25 focus:ring-offset-2 focus:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0",
        variants[variant],
        className,
      )}
      {...props}
    />
  ),
);

Button.displayName = "Button";
