interface PersonBadgeProps {
  code: string;
  role: "participant" | "moderator" | "observer";
  name?: string;
  highlighted?: boolean;
  /** Number only, tight (theme/molecules/person-badge.css): for a row of sessions
   *  or participants in a narrow place. */
  compact?: boolean;
  /** Not present here (not asked, did not speak): the outline, muted, no fill. */
  absent?: boolean;
  href?: string;
  "data-testid"?: string;
}

export function PersonBadge({
  code,
  name,
  highlighted,
  compact,
  absent,
  href,
  "data-testid": testId,
}: PersonBadgeProps) {
  const content = (
    <span
      className={`bn-person-badge${highlighted ? " bn-person-badge-highlighted" : ""}${
        compact ? " bn-person-badge-compact" : ""}${absent ? " bn-person-badge-absent" : ""}`}
      data-testid={testId}
    >
      <span className="bn-speaker-badge--split">
        <span className="bn-speaker-badge-code">{code}</span>
        {name && <span className="bn-speaker-badge-name">{name}</span>}
      </span>
    </span>
  );

  if (href) {
    return <a href={href} className="speaker-link">{content}</a>;
  }

  return content;
}
