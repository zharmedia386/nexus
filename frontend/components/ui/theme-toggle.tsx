"use client";

import { useSyncExternalStore } from "react";
import { applyTheme, readTheme, subscribeTheme, type ThemeChoice } from "@/lib/theme";

const OPTIONS: { value: ThemeChoice; label: string; icon: string }[] = [
  { value: "light", label: "Light theme", icon: "M12 4V2m0 20v-2m8-8h2M2 12h2m13.66-5.66 1.41-1.41M4.93 19.07l1.41-1.41m0-11.32L4.93 4.93m14.14 14.14-1.41-1.41M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z" },
  { value: "dark", label: "Dark theme", icon: "M20 14.5A8 8 0 0 1 9.5 4 8 8 0 1 0 20 14.5Z" },
  { value: "system", label: "System theme", icon: "M4 5h16v11H4zM9 20h6m-3-4v4" },
];

export function ThemeToggle({ className = "" }: { className?: string }) {
  const theme = useSyncExternalStore(subscribeTheme, readTheme, () => "system" as ThemeChoice);

  return (
    <div role="group" aria-label="Color theme" className={`flex items-center gap-0.5 ${className}`}>
      {OPTIONS.map((option) => {
        const pressed = option.value === theme;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={pressed}
            aria-label={option.label}
            title={option.label}
            onClick={() => applyTheme(option.value)}
            className={`grid size-8 place-items-center rounded-pill transition-[background-color,color,transform] duration-150 ease-std active:scale-[.94] ${pressed ? "bg-paper/20 text-paper" : "text-paper/70 hover:text-paper"}`}
          >
            <svg viewBox="0 0 24 24" className="size-4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d={option.icon} />
            </svg>
          </button>
        );
      })}
    </div>
  );
}
