/**
 * Organisms / Toolbar — the Quotes lens's toolbar pieces in `.toolbar`, the
 * row the Toolbar island draws them in, with local state standing in for
 * QuotesStore. The island itself is not drawn: it reads and writes the open
 * project's real filter state, which a style guide must not change.
 */

import { useState } from "react";

import { Icon } from "../../../components/Icon";
import { SearchBox } from "../../../components/SearchBox";
import { ToolbarButton } from "../../../components/ToolbarButton";
import { ViewSwitcher } from "../../../components/ViewSwitcher";
import type { SpecimenMeta, SpecimenStory } from "../csf";
import { Measured } from "../measure";

export default {
  title: "Organisms/Toolbar",
  description:
    "SearchBox, ViewSwitcher and ToolbarButton in .toolbar (organisms/toolbar.css), as islands/Toolbar.tsx lays them out.",
  caveat:
    "Live, on local state: type, collapse the search, switch the view. The Mac app draws no in-report toolbar (search and Starred live in the native toolbar).",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Row"] as const;

function LiveToolbar() {
  const [query, setQuery] = useState("");
  const [view, setView] = useState<"all" | "starred">("all");
  return (
    <div className="toolbar">
      <SearchBox value={query} onChange={setQuery} />
      <ViewSwitcher viewMode={view} onViewModeChange={setView} />
      <ToolbarButton label="Export" icon={<Icon name="export" px={14} decorative />} />
    </div>
  );
}

export const Row: SpecimenStory = {
  name: "Search, view switcher, export (live)",
  render: () => (
    <Measured selectors={[".toolbar", ".toolbar .toolbar-btn"]}>
      <LiveToolbar />
    </Measured>
  ),
};
