/**
 * Atoms / Buttons — the toolbar button family (`components/ToolbarButton.tsx`)
 * with the props the toolbar passes it. (The eye toggle is drawn only inside a
 * tag-sidebar group, so it belongs with that organism, not here.)
 */

import { useState } from "react";

import { Icon } from "../../../components/Icon";
import { ToolbarButton } from "../../../components/ToolbarButton";
import type { SpecimenMeta, SpecimenStory } from "../csf";

export default {
  title: "Atoms/Buttons",
  description:
    "ToolbarButton (atoms/button.css, atoms/toggle.css) as Toolbar, DisplayMenu and ViewSwitcher use it.",
  caveat:
    "Hover and focus are the browser's own: point at a button or Tab to it. Shown bare, outside the .toolbar row that spaces them in the app.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Toolbar", "Toggle"] as const;

export const Toolbar: SpecimenStory = {
  name: "Toolbar button",
  render: () => (
    <div className="bn-sg-specimens">
      <ToolbarButton label="Export" />
      <ToolbarButton label="Display" icon={<Icon name="display" px={14} decorative />} arrow />
      <ToolbarButton label="Display" icon={<Icon name="display" px={14} decorative />} arrow expanded />
      <ToolbarButton label="Export" disabled />
    </div>
  ),
};

function FocusToggle() {
  const [on, setOn] = useState(false);
  return (
    <ToolbarButton
      label="Focus mode"
      icon={<Icon name="focus" px={14} decorative />}
      className={on ? "toolbar-btn-toggle active" : "toolbar-btn-toggle"}
      aria-pressed={on}
      onClick={() => setOn((v) => !v)}
    />
  );
}

export const Toggle: SpecimenStory = {
  name: "Toggle (off, on, live)",
  render: () => (
    <div className="bn-sg-specimens">
      <ToolbarButton label="Focus mode" icon={<Icon name="focus" px={14} decorative />} className="toolbar-btn-toggle" aria-pressed={false} />
      <ToolbarButton label="Focus mode" icon={<Icon name="focus" px={14} decorative />} className="toolbar-btn-toggle active" aria-pressed />
      <FocusToggle />
    </div>
  ),
};
