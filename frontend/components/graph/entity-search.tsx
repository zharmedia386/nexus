"use client";

import { useEffect, useState, type KeyboardEvent } from "react";
import { TypeSwatch, typeLabel } from "@/components/graph/node-glyph";
import { api } from "@/lib/api";
import type { EntitySearchResult } from "@/lib/types";

export const DEBOUNCE_MS = 250;

const fold = (text: string) => text.normalize("NFKD").replace(/\p{M}/gu, "").toLowerCase().trim();

// The backend matches on name or alias; surface the alias when the name alone does not explain the hit.
export function matchedAlias(row: EntitySearchResult, query: string) {
  const needle = fold(query);
  if (fold(row.name).includes(needle)) return null;
  return row.aliases.find((alias) => fold(alias).includes(needle)) ?? null;
}

type SearchState = { status: "idle" } | { status: "error" } | { status: "done"; query: string; rows: EntitySearchResult[] };

type EntitySearchProps = {
  id: string;
  label: string;
  placeholder: string;
  defaultValue?: string;
  onPick: (entity: EntitySearchResult) => void;
};

export function EntitySearch({ id, label, placeholder, defaultValue = "", onPick }: EntitySearchProps) {
  const [query, setQuery] = useState(defaultValue);
  const [dirty, setDirty] = useState(false);
  const [search, setSearch] = useState<SearchState>({ status: "idle" });
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const listId = `${id}-listbox`;
  const rows = search.status === "done" ? search.rows : [];
  const ready = open && dirty && query.trim().length >= 2;
  const showList = ready && rows.length > 0;
  const message =
    search.status === "error" ? "Search is unavailable. Is the API running?" : search.status === "done" && rows.length === 0 ? `No entity matches “${search.query}”.` : "";

  useEffect(() => {
    const text = query.trim();
    if (!dirty || text.length < 2) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const found = await api.search(text, 8, controller.signal);
        setSearch({ status: "done", query: text, rows: found });
        setActive(found.length ? 0 : -1);
        setOpen(true);
      } catch {
        if (!controller.signal.aborted) setSearch({ status: "error" });
      }
    }, DEBOUNCE_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, dirty]);

  const pick = (row: EntitySearchResult) => {
    setQuery(row.name);
    setDirty(false);
    setOpen(false);
    onPick(row);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!rows.length) return;
      event.preventDefault();
      setOpen(true);
      const step = event.key === "ArrowDown" ? 1 : -1;
      setActive((current) => (current + step + rows.length) % rows.length);
    } else if (event.key === "Enter" && showList && rows[active]) {
      event.preventDefault();
      pick(rows[active]);
    } else if (event.key === "Escape" && showList) {
      event.preventDefault();
      setOpen(false);
    }
  };

  return (
    <div className="relative">
      <label htmlFor={id} className="mb-1.5 block text-caption text-muted-fg">{label}</label>
      <div className="relative">
        <svg viewBox="0 0 16 16" className="pointer-events-none absolute top-1/2 left-4 size-4 -translate-y-1/2 text-muted-fg" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden="true">
          <circle cx="7" cy="7" r="4.5" />
          <path d="m10.5 10.5 3 3" />
        </svg>
        <input
          id={id}
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? `${id}-option-${active}` : undefined}
          autoComplete="off"
          spellCheck={false}
          value={query}
          placeholder={placeholder}
          onChange={(event) => {
            setQuery(event.target.value);
            setDirty(true);
            // Drop the previous results so Enter never picks a row for an older query.
            setSearch({ status: "idle" });
            setActive(-1);
            setOpen(true);
          }}
          onKeyDown={onKeyDown}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          className="h-11 w-full rounded-pill border border-line bg-bg pr-4 pl-10 text-body text-fg transition-[border-color] duration-150 ease-std placeholder:text-muted-fg hover:border-ash focus-visible:border-ring"
        />
      </div>
      <ul
        id={listId}
        role="listbox"
        aria-label={`${label} results`}
        hidden={!showList}
        className="absolute inset-x-0 top-full z-30 mt-2 max-h-80 overflow-y-auto rounded-panel border border-line bg-bg p-1.5 shadow-soft"
      >
        {rows.map((row, index) => {
          const alias = matchedAlias(row, search.status === "done" ? search.query : query);
          return (
            <li
              key={row.id}
              id={`${id}-option-${index}`}
              role="option"
              aria-selected={index === active}
              // Keep focus in the input so the click lands before blur closes the list.
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => pick(row)}
              onMouseMove={() => setActive(index)}
              className={`flex cursor-pointer items-center gap-3 rounded-control px-3 py-2 ${index === active ? "bg-surface" : ""}`}
            >
              <TypeSwatch type={row.type} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-body text-fg">{row.name}</span>
                {alias ? <span className="block truncate text-caption text-muted-fg">alias · {alias}</span> : null}
              </span>
              <span className="shrink-0 text-caption text-muted-fg">{typeLabel(row.type)}</span>
            </li>
          );
        })}
      </ul>
      <p
        role="status"
        className={ready && message ? "absolute inset-x-0 top-full z-30 mt-2 rounded-panel border border-line bg-bg px-4 py-3 text-ui text-muted-fg shadow-soft" : "sr-only"}
      >
        {ready ? message : ""}
      </p>
    </div>
  );
}
