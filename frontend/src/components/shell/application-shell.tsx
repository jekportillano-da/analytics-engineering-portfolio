"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { LifecycleRail } from "@/components/lifecycle/lifecycle-rail";
import { lifecycleStages } from "@/lib/navigation/lifecycle";

export function ApplicationShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [presentationMode, setPresentationMode] = useState(false);
  const stageIndex = lifecycleStages.findIndex((stage) => pathname === `/${stage.id}`);
  const previous = lifecycleStages[stageIndex - 1];
  const next = lifecycleStages[stageIndex + 1];

  return (
    <div className={`application-shell${presentationMode ? " presentation-mode" : ""}`}>
      <header className="application-header">
        <div className="header-inner">
          <div className="header-topline">
            <div className="product-identity">
              <p className="product-name">THREADLINE</p>
              <p className="product-subtitle">Analytics Engineering Platform</p>
            </div>
            <button aria-pressed={presentationMode} className="presentation-toggle" onClick={() => setPresentationMode((value) => !value)} type="button">
              {presentationMode ? "Exit presentation" : "Presentation mode"}
            </button>
          </div>
          <LifecycleRail pathname={pathname} />
          {presentationMode && stageIndex >= 0 && <nav aria-label="Presentation sequence" className="presentation-controls"><span>{lifecycleStages[stageIndex].title} {stageIndex + 1}/6</span>{previous ? <Link href={`/${previous.id}`}>Previous</Link> : <span />}{next ? <Link href={`/${next.id}`}>Next</Link> : <span />}</nav>}
        </div>
      </header>
      {children}
      <footer className="application-footer"><div><strong>THREADLINE</strong><span>Analytics Engineering Platform</span></div><p>Built as an end-to-end analytics engineering portfolio.</p></footer>
    </div>
  );
}