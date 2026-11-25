import type { ButtonHTMLAttributes } from "react";

type Variant = "primary" | "secondary" | "light" | "ghost";

const VARIANTS: Record<Variant, string> = {
  primary: "bg-inverse-bg text-inverse-fg hover:opacity-90",
  secondary: "bg-surface text-fg hover:bg-line",
  light: "bg-paper text-carbon hover:bg-fog",
  ghost: "text-fg hover:bg-surface",
};

export function buttonClass(variant: Variant = "primary", className = "") {
  return `inline-flex h-11 items-center justify-center gap-2 rounded-pill px-[22px] text-body font-medium whitespace-nowrap transition-[transform,background-color,opacity] duration-150 ease-std active:scale-[.97] disabled:pointer-events-none disabled:opacity-50 ${VARIANTS[variant]} ${className}`;
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant };

export function Button({ variant, className, type = "button", ...props }: ButtonProps) {
  return <button type={type} className={buttonClass(variant, className)} {...props} />;
}
