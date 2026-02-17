import { Badge } from "./Badge";

export interface AnnotationTag {
  name: string;
  colour?: string;
}

interface AnnotationProps {
  quoteId: string;
  label?: string;
  sentiment?: { text: string; sentiment: string; onDelete?: () => void };
  tags?: AnnotationTag[];
  onTagDelete?: (tagName: string) => void;
  className?: string;
  "data-testid"?: string;
}

export function Annotation({
  quoteId,
  label,
  sentiment,
  tags,
  onTagDelete,
  className,
  "data-testid": testId,
}: AnnotationProps) {
  const hasTags = (tags && tags.length > 0) || sentiment;
  if (!label && !hasTags) return null;

  const classes = ["margin-annotation", className].filter(Boolean).join(" ");

  return (
    <div className={classes} data-quote-id={quoteId} data-testid={testId}>
      {label && (
        <a className="margin-label" href={`#q-${quoteId}`}>
          {label}
        </a>
      )}
      {hasTags && (
        <div className="margin-tags">
          {sentiment && (
            <Badge
              variant="ai"
              text={sentiment.text}
              sentiment={sentiment.sentiment}
              onDelete={sentiment.onDelete}
              data-testid={testId ? `${testId}-sentiment` : undefined}
            />
          )}
          {tags?.map((tag) => (
            <Badge
              key={tag.name}
              variant="user"
              text={tag.name}
              colour={tag.colour}
              onDelete={onTagDelete ? () => onTagDelete(tag.name) : undefined}
              data-testid={testId ? `${testId}-tag-${tag.name}` : undefined}
            />
          ))}
        </div>
      )}
    </div>
  );
}
