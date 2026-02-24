interface PersonBadgeProps {
  code: string;
  role: "participant" | "moderator" | "observer";
  name?: string;
  highlighted?: boolean;
  href?: string;
  "data-testid"?: string;
}

export function PersonBadge({
  code,
  name,
  highlighted,
  href,
  "data-testid": testId,
}: PersonBadgeProps) {
  const content = (
    <span
      className={`bn-person-badge${highlighted ? " bn-person-badge-highlighted" : ""}`}
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
