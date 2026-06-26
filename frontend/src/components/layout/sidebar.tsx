import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { BrainCircuit } from "lucide-react";

import { cn } from "@/lib/cn";
import { navLinks } from "@/components/layout/nav-links";

export function Sidebar() {
  const { t } = useTranslation();

  return (
    <aside className="sticky top-0 hidden h-screen w-72 shrink-0 border-e border-border/65 bg-card/80 px-4 py-5 shadow-panel backdrop-blur-xl lg:flex lg:flex-col">
      <div className="mb-7 rounded-2xl border border-border/65 bg-muted/45 p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-primary text-white shadow-glow dark:text-slate-950">
            <BrainCircuit size={24} />
          </div>
          <div>
            <p className="text-xs font-bold uppercase text-foreground/45">
              Mentis
            </p>
            <h1 className="mt-1 text-base font-extrabold leading-6">
              {t("app.name")}
            </h1>
          </div>
        </div>
      </div>
      <nav className="space-y-1.5">
        {navLinks.map(({ to, icon: Icon, key }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              cn(
                "group flex items-center gap-3 rounded-xl border px-3.5 py-3 text-sm font-bold transition duration-200",
                isActive
                  ? "border-primary/20 bg-primary/10 text-primary shadow-sm"
                  : "border-transparent text-foreground/66 hover:border-border/70 hover:bg-muted/70 hover:text-foreground",
              )
            }
          >
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-card/80 text-foreground/70 transition group-hover:text-primary">
              <Icon size={18} />
            </span>
            <span>{t(key)}</span>
          </NavLink>
        ))}
      </nav>
      <div className="mt-auto rounded-2xl border border-border/65 bg-surface/60 p-4">
        <p className="text-xs font-semibold leading-6 text-foreground/60">
          {t("dashboard.subtitle")}
        </p>
      </div>
    </aside>
  );
}
