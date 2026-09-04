"use client";

import * as Dialog from "@radix-ui/react-dialog";
import * as Tooltip from "@radix-ui/react-tooltip";
import type { TechnicalDetail } from "@/content/journey-content";

export function TechnicalTerm({ children, detail }: { children: React.ReactNode; detail: TechnicalDetail }) {
  return (
    <Dialog.Root>
      <Tooltip.Provider delayDuration={150}>
        <Tooltip.Root>
          <Tooltip.Trigger asChild>
            <Dialog.Trigger className="technical-term" type="button">{children}</Dialog.Trigger>
          </Tooltip.Trigger>
          <Tooltip.Portal>
            <Tooltip.Content className="tooltip-content" side="top" sideOffset={8}>{detail.summary}</Tooltip.Content>
          </Tooltip.Portal>
        </Tooltip.Root>
      </Tooltip.Provider>
      <Dialog.Portal>
        <Dialog.Overlay className="technical-drawer-overlay" />
        <Dialog.Content className="technical-drawer">
          <div className="drawer-heading">
            <div>
              <Dialog.Title>{detail.title}</Dialog.Title>
              <Dialog.Description>{detail.summary}</Dialog.Description>
            </div>
            <Dialog.Close aria-label="Close technical detail" className="drawer-close" type="button">Close</Dialog.Close>
          </div>
          <p className="drawer-detail">{detail.detail}</p>
          <p className="drawer-reference">Repository reference: {detail.sourceReference}</p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}