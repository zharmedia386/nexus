"use client";

import { useEffect, useRef, useState } from "react";
import { REPO_URL } from "@/lib/routes";

type FilmProps = { src: string; poster: string; captions: string };

export function Film({ src, poster, captions }: FilmProps) {
  const video = useRef<HTMLVideoElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    // A load error that fires before hydration never reaches onError.
    const element = video.current;
    if (element && (element.error || element.networkState === HTMLMediaElement.NETWORK_NO_SOURCE)) setFailed(true);
  }, []);

  return (
    <div data-surface="dark" className="relative aspect-video overflow-hidden rounded-card bg-ink-night shadow-lift">
      {failed ? (
        <>
          {/* eslint-disable-next-line @next/next/no-img-element -- static poster, already sized by the frame */}
          <img src={poster} alt="" className="absolute inset-0 size-full object-cover opacity-15 md:opacity-35" />
          <div className="relative flex size-full items-end p-5 md:p-10">
            <p className="max-w-md text-body text-paper md:text-body-lg">
              The film is not published yet. Until it is, the{" "}
              <a href={`${REPO_URL}#readme`} target="_blank" rel="noreferrer" className="underline decoration-paper/40 underline-offset-4 hover:decoration-paper">
                README on GitHub<span className="sr-only"> (opens in a new tab)</span>
              </a>{" "}
              walks through the same setup with screenshots.
            </p>
          </div>
        </>
      ) : (
        <video ref={video} aria-label="NEXUS demo film" src={src} poster={poster} controls preload="metadata" playsInline onError={() => setFailed(true)} className="size-full object-cover">
          <track kind="captions" srcLang="en" label="English" src={captions} default />
        </video>
      )}
    </div>
  );
}

export function FilmSection() {
  return (
    <section id="film" aria-labelledby="film-title" className="mx-auto max-w-content scroll-mt-24 px-6 pt-24 md:pt-[104px]">
      <h2 id="film-title" className="text-heading font-normal md:text-heading-lg">The short version</h2>
      <p className="mt-4 mb-10 max-w-[60ch] text-body-lg text-muted-fg">A narrated run of the local stack, from corpus to cited answer. Captions included.</p>
      <Film src="/film/nexus-demo.mp4" poster="/film/nexus-demo-poster.png" captions="/film/nexus-demo.en.vtt" />
    </section>
  );
}
