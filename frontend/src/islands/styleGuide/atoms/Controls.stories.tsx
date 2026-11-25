/**
 * Atoms / Choosers and media — the segmented control the dialogs use, the
 * compact selector the transcript page uses to switch session, and the
 * session thumbnail.
 */

import { useState } from "react";

import { SegmentedTabs } from "../../../components/SegmentedTabs";
import { Selector } from "../../../components/Selector";
import { Thumbnail } from "../../../components/Thumbnail";
import type { SpecimenMeta, SpecimenStory } from "../csf";

export default {
  title: "Atoms/Choosers and media",
  description:
    "SegmentedTabs (.bn-seg in atoms/modal.css), Selector (.bn-selector in templates/transcript.css) and Thumbnail (atoms/thumbnail.css).",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Segmented", "SessionSelector", "Thumbnails"] as const;

function LiveSegmented() {
  const [route, setRoute] = useState<"app" | "token">("app");
  return (
    <div>
      <span id="bn-sg-seg-label" className="bn-sg-note">
        Connect with
      </span>
      <SegmentedTabs
        tabs={[
          { key: "app", label: "The Miro app" },
          { key: "token", label: "An access token" },
        ]}
        selected={route}
        onSelect={setRoute}
        labelledBy="bn-sg-seg-label"
        idPrefix="bn-sg-seg"
      />
    </div>
  );
}

export const Segmented: SpecimenStory = {
  name: "Segmented tabs (live)",
  render: () => <LiveSegmented />,
};

interface FixtureSession {
  id: string;
  label: string;
}

const SESSIONS: FixtureSession[] = [
  { id: "s1", label: "Session 1 · p1 Sarah Chen" },
  { id: "s2", label: "Session 2 · p2 Mary Adeyemi" },
  { id: "s3", label: "Session 3 · p3 Dr Amara Nwosu" },
];

function LiveSelector() {
  const [active, setActive] = useState("s2");
  return (
    <Selector<FixtureSession>
      label={SESSIONS.find((s) => s.id === active)?.label.split(" · ")[0] ?? "Session"}
      items={SESSIONS}
      itemKey={(s) => s.id}
      renderItem={(s) => <span>{s.label}</span>}
      activeKey={active}
      onSelect={(s) => setActive(s.id)}
      className="bn-session-selector"
    />
  );
}

export const SessionSelector: SpecimenStory = {
  name: "Session selector (live)",
  render: () => <LiveSelector />,
};

export const Thumbnails: SpecimenStory = {
  name: "Thumbnail: a recording whose frame has not been drawn (a session with no recording draws nothing)",
  render: () => (
    <div className="bn-sg-specimens">
      <Thumbnail hasMedia title="session-2.mp4" />
    </div>
  ),
};
