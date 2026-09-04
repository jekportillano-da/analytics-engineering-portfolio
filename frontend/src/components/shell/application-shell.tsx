"use client";

import { usePathname } from "next/navigation";
import { LifecycleRail } from "@/components/lifecycle/lifecycle-rail";

export function ApplicationShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="application-shell">
      <header className="application-header">
        <div className="header-inner">
          <div className="product-identity">
            <p className="product-name">THREADLINE</p>
            <p className="product-subtitle">Analytics Engineering Platform</p>
          </div>
          <LifecycleRail pathname={usePathname()} />
        </div>
      </header>
      {children}
    </div>
  );
}