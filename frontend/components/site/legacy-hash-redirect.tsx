"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { legacyHashTarget } from "@/lib/routes";

export function LegacyHashRedirect() {
  const router = useRouter();

  useEffect(() => {
    const target = legacyHashTarget(window.location.hash, window.location.search);
    if (target) router.replace(target);
  }, [router]);

  return null;
}
