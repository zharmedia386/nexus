import type { HTMLAttributes } from "react";

type ChipProps = HTMLAttributes<HTMLSpanElement> & { mono?: boolean };

export function Chip({ mono = false, className = "", ...props }: ChipProps) {
  return (
    <span
      className={`inline-flex h-7 items-center gap-1.5 rounded-pill border border-line px-3 ${mono ? "font-mono text-mono" : "text-ui"} ${className}`}
      {...props}
    />
  );
}
