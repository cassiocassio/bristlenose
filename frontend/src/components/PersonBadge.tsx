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
    <div
      className={`bn-person-badge${highlighted ? " bn-person-badge-highlighted" : ""}`}
      data-testid={testId}
    >
      <span className="badge">{code}</span>
      {name && <span className="bn-person-badge-name">{name}</span>}
    </div>
  );

  if (href) {
    return <a href={href}>{content}</a>;
  }

  return content;
}
