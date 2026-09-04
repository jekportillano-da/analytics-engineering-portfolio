"use client";

import { usePathname } from "next/navigation";
import { LifecycleRail } from "@/components/lifecycle/lifecycle-rail";

export function ApplicationShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="application-shell">
      <header className="application-header">
        <div className="header-inner">
          <p className="product-identity">ANALYTICS ENGINEERING PLATFORM</p>
          <LifecycleRail pathname={usePathname()} />
        </div>
      </header>
      {children}
    </div>
  );
}