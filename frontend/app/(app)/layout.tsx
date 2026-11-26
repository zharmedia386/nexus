import type { ReactNode } from "react";
import { AppNav } from "@/components/site/app-nav";

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <>
      <AppNav />
      {children}
    </>
  );
}
