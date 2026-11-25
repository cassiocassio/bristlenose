/**
 * Atoms / Person badge — `components/PersonBadge.tsx`, the speaker code (and
 * name) wherever a person is cited: quote cards, sessions table, transcripts.
 */

import { PersonBadge } from "../../../components/PersonBadge";
import type { SpecimenMeta, SpecimenStory } from "../csf";

export default {
  title: "Atoms/Person badge",
  description: "The speaker badge (molecules/person-badge.css), one per role and state.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Roles", "States"] as const;

export const Roles: SpecimenStory = {
  name: "Roles, code only and with a name",
  render: () => (
    <div className="bn-sg-specimens">
      <PersonBadge code="p1" role="participant" />
      <PersonBadge code="p1" role="participant" name="Sarah Chen" />
      <PersonBadge code="m1" role="moderator" />
      <PersonBadge code="m1" role="moderator" name="Marcus Bell" />
      <PersonBadge code="o1" role="observer" />
      <PersonBadge code="o1" role="observer" name="Jane Smith" />
    </div>
  ),
};

export const States: SpecimenStory = {
  name: "Highlighted, compact, absent, linked",
  render: () => (
    <div className="bn-sg-specimens">
      <PersonBadge code="p2" role="participant" name="Mary Adeyemi" highlighted />
      <PersonBadge code="p2" role="participant" compact />
      <PersonBadge code="p3" role="participant" absent />
      <PersonBadge code="p3" role="participant" name="Dr Amara Nwosu" href="#atoms-person-badge" />
    </div>
  ),
};
