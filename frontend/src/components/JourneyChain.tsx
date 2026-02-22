import { useCallback, useEffect, useRef, useState } from "react";

interface JourneyChainProps {
  labels: string[];
  separator?: string;
  className?: string;
  "data-testid"?: string;
  /** When set, the matching label gets `.bn-journey-label--active`. */
  activeLabel?: string | null;
  /** If provided, labels become clickable (rendered as buttons for a11y). */
  onLabelClick?: (label: string) => void;
  /** Enable horizontal scroll with hidden scrollbar and edge fade masks. */
  stickyOverflow?: boolean;
}

export function JourneyChain({
  labels,
  separator = " \u2192 ",
  className,
  "data-testid": testId,
  activeLabel,
  onLabelClick,
  stickyOverflow,
}: JourneyChainProps) {
  if (labels.length === 0) return null;

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const labelRefs = useRef<Map<string, HTMLElement>>(new Map());
  const [canScrollLeft, setCanScrollLeft] = useState(false);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const isInteractive = !!onLabelClick;

  // Track overflow state for fade masks
  const updateOverflow = useCallback(() => {
    const el = scrollRef.current;
    if (!el) return;
    setCanScrollLeft(el.scrollLeft > 1);
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 1);
  }, []);

  useEffect(() => {
    if (!stickyOverflow) return;
    const el = scrollRef.current;
    if (!el) return;

    updateOverflow();
    el.addEventListener("scroll", updateOverflow, { passive: true });

    let ro: ResizeObserver | null = null;
    if (typeof ResizeObserver !== "undefined") {
      ro = new ResizeObserver(updateOverflow);
      ro.observe(el);
    }

    return () => {
      el.removeEventListener("scroll", updateOverflow);
      ro?.disconnect();
    };
  }, [stickyOverflow, updateOverflow, labels]);

  // Auto-scroll active label into view
  useEffect(() => {
    if (!stickyOverflow || !activeLabel) return;
    const labelEl = labelRefs.current.get(activeLabel);
    if (labelEl) {
      labelEl.scrollIntoView({ inline: "center", behavior: "smooth", block: "nearest" });
    }
  }, [activeLabel, stickyOverflow]);

  // Build container classes
  const containerClasses = [
    "bn-session-journey",
    stickyOverflow && "bn-session-journey--overflow",
    stickyOverflow && canScrollLeft && canScrollRight && "bn-journey--fade-both",
    stickyOverflow && canScrollLeft && !canScrollRight && "bn-journey--fade-left",
    stickyOverflow && !canScrollLeft && canScrollRight && "bn-journey--fade-right",
    className,
  ]
    .filter(Boolean)
    .join(" ");

  const setLabelRef = (label: string, el: HTMLElement | null) => {
    if (el) {
      labelRefs.current.set(label, el);
    } else {
      labelRefs.current.delete(label);
    }
  };

  return (
    <div
      className={containerClasses}
      data-testid={testId}
      ref={stickyOverflow ? scrollRef : undefined}
    >
      {labels.map((label, i) => {
        const isActive = activeLabel === label;
        const labelClasses = [
          "bn-journey-label",
          isInteractive && "bn-journey-label--interactive",
          isActive && "bn-journey-label--active",
        ]
          .filter(Boolean)
          .join(" ");

        return (
          <span key={i}>
            {i > 0 && (
              <span className="bn-journey-sep" aria-hidden="true">
                {separator}
              </span>
            )}
            {isInteractive ? (
              <button
                type="button"
                className={labelClasses}
                onClick={() => onLabelClick!(label)}
                ref={(el) => setLabelRef(label, el)}
                aria-current={isActive ? "step" : undefined}
                data-testid={testId ? `${testId}-label-${i}` : undefined}
              >
                {label}
              </button>
            ) : (
              <span
                className={labelClasses}
                ref={(el) => setLabelRef(label, el)}
                data-testid={testId ? `${testId}-label-${i}` : undefined}
              >
                {label}
              </span>
            )}
          </span>
        );
      })}
    </div>
  );
}
