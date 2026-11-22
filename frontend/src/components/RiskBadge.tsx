import { CircleAlert, CircleCheck, TriangleAlert } from "lucide-react";
import { LEVEL_LABEL } from "../domain/labels";
import { riskLevel } from "../domain/risk";
import { fmtScore } from "../lib/format";
import { cn } from "./ui/cn";

const STYLE = {
  high: "border-risk-high/40 bg-risk-high/10 text-risk-high",
  medium: "border-risk-mid/40 bg-risk-mid/10 text-risk-mid",
  low: "border-risk-low/40 bg-risk-low/10 text-risk-low",
} as const;

export function RiskBadge({ score }: { score: number }) {
  const level = riskLevel(score);
  const Icon = level === "high" ? TriangleAlert : level === "medium" ? CircleAlert : CircleCheck;
  return (
    <span className={cn("inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-xs font-medium", STYLE[level])}>
      <Icon className="h-3 w-3" aria-hidden />
      {LEVEL_LABEL[level]}
      <span className="font-mono font-normal opacity-80">{fmtScore(score)}</span>
    </span>
  );
}
