"use client";

import * as Tooltip from "@radix-ui/react-tooltip";
import Link from "next/link";
import { useEffect, useRef } from "react";
import { lifecycleStages } from "@/lib/navigation/lifecycle";

export function LifecycleRail({ pathname }: { pathname: string }) {
  const activeStageRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    activeStageRef.current?.scrollIntoView({ block: "nearest", inline: "center" });
  }, [pathname]);

  return (
    <nav aria-label="Analytics platform lifecycle" className="lifecycle-viewport">
      <Tooltip.Provider delayDuration={150}>
        <ol className="lifecycle-rail lifecycle-track">
          {lifecycleStages.map((stage) => {
            const isActive = pathname === `/${stage.id}`;
            return (
              <li className="lifecycle-stage" key={stage.id}>
                <Tooltip.Root>
                  <Tooltip.Trigger asChild>
                    <Link
                      aria-current={isActive ? "page" : undefined}
                      className="lifecycle-link"
                      href={`/${stage.id}`}
                      ref={isActive ? activeStageRef : undefined}
                    >
                      <span aria-hidden="true" className="lifecycle-marker" />
                      <span>{stage.title}</span>
                    </Link>
                  </Tooltip.Trigger>
                  <Tooltip.Portal>
                    <Tooltip.Content className="tooltip-content" side="bottom" sideOffset={10}>
                      {stage.tooltip}
                    </Tooltip.Content>
                  </Tooltip.Portal>
                </Tooltip.Root>
              </li>
            );
          })}
        </ol>
      </Tooltip.Provider>
    </nav>
  );
}