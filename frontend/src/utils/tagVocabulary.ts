import type { CodebookGroupResponse } from "./types";
import type { TagVocabularyGroup } from "../components/TagInput";

/**
 * The tag picker's grouped vocabulary, from the codebook.
 *
 * Each tag carries its row id, so a pick commits the tag chosen rather than a name two tags can
 * share, and each group its `framework_id` (null for the researcher's own). The researcher's own
 * groups are listed first (N146): their tags are hard-won and the codebook's are cheap to reach,
 * so the one they made leads when both answer to a name. The sort is stable, so the codebook's
 * own order holds within each kind.
 */
export function buildTagVocabulary(groups: CodebookGroupResponse[]): TagVocabularyGroup[] {
  const built: TagVocabularyGroup[] = groups.map((g) => ({
    groupName: g.name,
    colourSet: g.colour_set,
    frameworkId: g.framework_id,
    tags: g.tags.map((tg) => ({ name: tg.name, colourIndex: tg.colour_index, id: tg.id })),
  }));
  return built
    .map((g, i) => ({ g, i }))
    .sort((a, b) => Number(a.g.frameworkId !== null) - Number(b.g.frameworkId !== null) || a.i - b.i)
    .map(({ g }) => g);
}
