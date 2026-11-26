import { FilmSection } from "@/components/landing/film";
import { Hero } from "@/components/landing/hero";
import { Modes } from "@/components/landing/modes";
import { Pipeline } from "@/components/landing/pipeline";
import { Proof } from "@/components/landing/proof";
import { RunIt } from "@/components/landing/run-it";
import { Walkthrough } from "@/components/landing/walkthrough";
import { LegacyHashRedirect } from "@/components/site/legacy-hash-redirect";

export default function HomePage() {
  return (
    <>
      <LegacyHashRedirect />
      <Hero />
      <FilmSection />
      <Walkthrough />
      <Modes />
      <Proof />
      <Pipeline />
      <RunIt />
    </>
  );
}
