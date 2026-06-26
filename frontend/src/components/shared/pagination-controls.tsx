import { ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";

import { Button } from "@/components/shared/button";
import { Select } from "@/components/shared/select";

export const PAGE_SIZE_OPTIONS = [5, 10, 25, 50, 100] as const;

type PaginationControlsProps = {
  page: number;
  pageSize: number;
  total: number;
  isFetching?: boolean;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
};

export function PaginationControls({
  page,
  pageSize,
  total,
  isFetching = false,
  onPageChange,
  onPageSizeChange,
}: PaginationControlsProps) {
  const { t } = useTranslation();
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  if (!total) {
    return null;
  }

  return (
    <div className="mt-4 flex flex-col gap-3 border-t border-border/40 pt-4 lg:flex-row lg:items-center lg:justify-between">
      <div className="flex flex-col gap-3 text-sm text-foreground/70 sm:flex-row sm:flex-wrap sm:items-center">
        <span className="inline-flex h-10 items-center rounded-full bg-muted px-4">
          {t("common.results")}: {total}
        </span>
        <span className="inline-flex h-10 items-center rounded-full bg-muted px-4">
          {t("common.page")} {page} {t("common.of")} {totalPages}
        </span>
        <label className="inline-flex h-10 items-center overflow-hidden rounded-full border border-border/70 bg-background shadow-sm transition focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/15">
          <span className="border-e border-border/60 px-4 text-foreground/70">
            {t("common.perPage")}
          </span>
          <span className="relative inline-flex h-full items-center">
            <Select
              value={String(pageSize)}
              onChange={(event) => onPageSizeChange(Number(event.target.value))}
              className="h-full w-20 appearance-none rounded-none border-0 bg-transparent pe-8 ps-4 text-center font-semibold text-foreground focus:border-transparent"
            >
              {PAGE_SIZE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
            <ChevronDown className="pointer-events-none absolute end-3 h-4 w-4 text-foreground/50" />
          </span>
        </label>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="secondary"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1 || isFetching}
        >
          {t("common.previous")}
        </Button>
        <Button
          type="button"
          variant="secondary"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages || isFetching}
        >
          {t("common.next")}
        </Button>
      </div>
    </div>
  );
}
