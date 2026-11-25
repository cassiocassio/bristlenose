/**
 * Organisms / Dialog and journey — the shell every modal draws through
 * (`components/Dialog.tsx`: backdrop, card, the ×, focus trap) and the user
 * journey chain the Sessions table and transcript page draw.
 */

import { useState } from "react";

import { Dialog } from "../../../components/Dialog";
import { JourneyChain } from "../../../components/JourneyChain";
import { ToolbarButton } from "../../../components/ToolbarButton";
import type { SpecimenMeta, SpecimenStory } from "../csf";

export default {
  title: "Organisms/Dialog and journey",
  description:
    "Dialog (atoms/modal.css: .bn-overlay, .bn-modal, .bn-modal-close) with fixture content, and JourneyChain (atoms/journey-label.css).",
  caveat:
    "The dialog opens over the page, as in the app: Escape or the × closes it; the backdrop never does. The content inside it is fixture text; each real dialog supplies its own.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["DialogShell", "Journey"] as const;

function DialogLauncher() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <ToolbarButton label="Open the dialog" onClick={() => setOpen(true)} />
      <Dialog open={open} onClose={() => setOpen(false)} labelledBy="bn-sg-dialog-title">
        <h2 id="bn-sg-dialog-title">Export the report</h2>
        <p>The report is saved as one HTML file that opens without Bristlenose.</p>
      </Dialog>
    </>
  );
}

export const DialogShell: SpecimenStory = {
  name: "Dialog shell (opens the real dialog)",
  render: () => <DialogLauncher />,
};

const JOURNEY = ["Home", "Search", "Product page", "Basket", "Checkout", "Delivery options", "Payment"];

function LiveJourney() {
  const [active, setActive] = useState(3);
  return <JourneyChain labels={JOURNEY} activeIndex={active} onIndexClick={setActive} />;
}

export const Journey: SpecimenStory = {
  name: "Journey chain: plain, and clickable with the current step (live)",
  render: () => (
    <div className="bn-sg-stack">
      <JourneyChain labels={JOURNEY} />
      <LiveJourney />
    </div>
  ),
};
