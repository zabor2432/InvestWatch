import { STATUS_LABEL } from "../domain/labels";
import type { RecordStatus } from "../domain/types";
import { cn } from "./ui/cn";

const DOT: Record<RecordStatus, string> = {
  new: "bg-accent",
  in_review: "bg-risk-mid",
  confirmed: "bg-risk-high",
  false_positive: "bg-muted",
};

export function StatusBadge({ status }: { status: RecordStatus }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span className={cn("h-2 w-2 rounded-full", DOT[status])} aria-hidden />
      {STATUS_LABEL[status]}
    </span>
  );
}
