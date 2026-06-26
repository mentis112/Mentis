import { ReactNode } from "react";
import { motion } from "framer-motion";

import { Card } from "@/components/shared/card";

export function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: string | number;
  icon: ReactNode;
}) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
      whileHover={{ y: -3 }}
    >
      <Card className="relative overflow-hidden p-5">
        <div className="absolute inset-x-0 top-0 h-1 bg-primary/70" />
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold text-foreground/60">{label}</p>
            <p className="mt-3 text-3xl font-extrabold">{value}</p>
          </div>
          <div className="rounded-xl border border-primary/15 bg-primary/10 p-3 text-primary">{icon}</div>
        </div>
      </Card>
    </motion.div>
  );
}
