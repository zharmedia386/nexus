"use client";

import { useLayoutEffect, useRef, type KeyboardEvent } from "react";

type Tab<T extends string> = { id: T; label: string };

type TabsProps<T extends string> = {
  tabs: Tab<T>[];
  value: T;
  onChange: (id: T) => void;
  label: string;
  className?: string;
};

export function Tabs<T extends string>({ tabs, value, onChange, label, className = "" }: TabsProps<T>) {
  const listRef = useRef<HTMLDivElement>(null);
  const pillRef = useRef<HTMLSpanElement>(null);
  const placedRef = useRef(false);

  useLayoutEffect(() => {
    const list = listRef.current;
    const pill = pillRef.current;
    if (!list || !pill) return;
    const place = (animate: boolean) => {
      const active = list.querySelector<HTMLElement>('[aria-selected="true"]');
      if (!active) return;
      // First paint and resizes snap into place; only user changes slide.
      if (!animate) pill.style.transition = "none";
      pill.style.width = `${active.offsetWidth}px`;
      pill.style.transform = `translateX(${active.offsetLeft}px)`;
      if (!animate) {
        void pill.offsetWidth;
        pill.style.transition = "";
      }
    };
    place(placedRef.current);
    placedRef.current = true;
    const observer = new ResizeObserver(() => place(false));
    observer.observe(list);
    return () => observer.disconnect();
  }, [value]);

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
    if (!step) return;
    event.preventDefault();
    const index = tabs.findIndex((tab) => tab.id === value);
    const next = tabs[(index + step + tabs.length) % tabs.length];
    onChange(next.id);
    listRef.current?.querySelector<HTMLElement>(`[data-tab="${next.id}"]`)?.focus();
  };

  return (
    <div
      ref={listRef}
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className={`relative inline-flex items-center gap-[3px] rounded-pill bg-surface p-[3px] ${className}`}
    >
      <span
        ref={pillRef}
        aria-hidden="true"
        className="absolute top-[3px] left-0 h-[34px] w-0 rounded-pill bg-bg shadow-[0_1px_2px_#0000001a] transition-[transform,width] duration-[250ms] ease-out will-change-transform"
      />
      {tabs.map((tab) => {
        const selected = tab.id === value;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            data-tab={tab.id}
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={`relative z-10 h-[34px] rounded-pill px-4 text-ui transition-colors duration-150 ease-std ${selected ? "font-medium text-fg" : "text-fg-2 hover:text-fg"}`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
