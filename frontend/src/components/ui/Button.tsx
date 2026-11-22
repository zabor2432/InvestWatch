import type { ButtonHTMLAttributes } from "react";
import { cn } from "./cn";

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "default" | "primary" | "ghost";
  size?: "sm" | "md";
}

export function Button({ variant = "default", size = "md", className, type = "button", ...rest }: Props) {
  return (
    <button
      type={type}
      className={cn(
        "inline-flex items-center justify-center gap-1.5 rounded border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        size === "sm" ? "h-7 px-2 text-xs" : "h-8 px-3 text-sm",
        variant === "default" && "border-line bg-surface hover:bg-raised",
        variant === "primary" && "border-accent bg-accent text-bg hover:opacity-90",
        variant === "ghost" && "border-transparent hover:bg-raised",
        className,
      )}
      {...rest}
    />
  );
}
