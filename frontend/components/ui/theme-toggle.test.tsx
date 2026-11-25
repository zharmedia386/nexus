import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { ThemeToggle } from "@/components/ui/theme-toggle";
import { THEME_KEY, THEME_SCRIPT } from "@/lib/theme";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeToggle", () => {
  it("defaults to system and leaves data-theme unset", () => {
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "System theme" })).toHaveAttribute("aria-pressed", "true");
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });

  it("persists an explicit choice and the head script restores it", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Dark theme" }));

    expect(localStorage.getItem(THEME_KEY)).toBe("dark");
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
    expect(screen.getByRole("button", { name: "Dark theme" })).toHaveAttribute("aria-pressed", "true");

    document.documentElement.removeAttribute("data-theme");
    new Function(THEME_SCRIPT)();
    expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  });

  it("returning to system clears storage so prefers-color-scheme applies", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Light theme" }));
    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "System theme" }));
    });

    expect(localStorage.getItem(THEME_KEY)).toBeNull();
    expect(document.documentElement).not.toHaveAttribute("data-theme");
  });
});
