import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { useInert } from "../hooks/useInert";
import { Icon } from "./Icon";
import { PanelErrorBoundary } from "./PanelErrorBoundary";
import { toast } from "../utils/toast";
import { DEFAULT_GITHUB_ISSUES_URL, type HealthResponse } from "../utils/health";

/**
 * Which journey brought the person to the form (`docs/design-feedback-native.md`
 * § Feedback and problem reports). Feedback is their own idea; a problem report
 * is Bristlenose suggesting it after something failed: its own heading and
 * label, what went wrong already in the message, and `kind: "problem"` on the
 * wire. The Mac twin is `FeedbackSheetMode`.
 */
export type FeedbackMode =
  | { kind: "feedback" }
  | { kind: "problem"; initialMessage: string };

const FEEDBACK: FeedbackMode = { kind: "feedback" };

interface FeedbackModalProps {
  open: boolean;
  onClose: () => void;
  health: HealthResponse;
  /** Feedback unless a failure pane opens it. */
  mode?: FeedbackMode;
}

const FEEDBACK_DRAFT_KEY = "bristlenose-feedback-draft";

const FEEDBACK_SENTIMENT_KEYS: { value: string; emoji: string; labelKey: string }[] = [
  { value: "hate", emoji: "\uD83D\uDE20", labelKey: "feedback.sentimentHate" },
  { value: "dislike", emoji: "\uD83D\uDE15", labelKey: "feedback.sentimentDislike" },
  { value: "neutral", emoji: "\uD83D\uDE10", labelKey: "feedback.sentimentNeutral" },
  { value: "like", emoji: "\uD83D\uDE42", labelKey: "feedback.sentimentLike" },
  { value: "love", emoji: "\uD83D\uDE0A", labelKey: "feedback.sentimentLove" },
];

interface DraftData {
  rating: string;
  message: string;
}

function readDraft(): DraftData {
  try {
    const raw = localStorage.getItem(FEEDBACK_DRAFT_KEY);
    if (!raw) return { rating: "", message: "" };
    const parsed = JSON.parse(raw) as Partial<DraftData>;
    return {
      rating: parsed.rating ?? "",
      message: parsed.message ?? "",
    };
  } catch {
    return { rating: "", message: "" };
  }
}

function writeDraft(draft: DraftData): void {
  try {
    localStorage.setItem(FEEDBACK_DRAFT_KEY, JSON.stringify(draft));
  } catch {
    /* storage unavailable (private mode / quota) — draft is best-effort */
  }
}

export function FeedbackModal({ open, onClose, health, mode = FEEDBACK }: FeedbackModalProps) {
  const { t, i18n } = useTranslation();
  useInert(open);
  const isProblem = mode.kind === "problem";
  const initialMessage = mode.kind === "problem" ? mode.initialMessage : "";
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [rating, setRating] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);
  // The locale key of the sentence a failed send leaves in the form (R80):
  // it wasn't sent, where the copy is, and where to paste it.
  const [failure, setFailure] = useState<string | null>(null);
  // The send in flight. Closing the form aborts it, so a send that ends after
  // the person has left touches nothing: no clipboard, no toast, no second
  // onClose, no wiped draft (the Mac sheet's Task.isCancelled guards).
  const inFlight = useRef<AbortController | null>(null);

  const close = useCallback(() => {
    inFlight.current?.abort();
    inFlight.current = null;
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (open) return;
    // Closed from outside (or by `close` above): drop the send in flight.
    // Its `sending` is reset when the form next opens.
    inFlight.current?.abort();
    inFlight.current = null;
  }, [open]);

  useEffect(() => () => inFlight.current?.abort(), []);

  useEffect(() => {
    if (!open) return;
    // A problem report starts from what went wrong, with a blank line under it
    // and the caret there, and leaves the feedback draft alone: it neither
    // inherits a half-written note nor overwrites it.
    if (isProblem) {
      setRating("");
      setMessage(initialMessage + "\n\n");
    } else {
      const draft = readDraft();
      setRating(draft.rating);
      setMessage(draft.message);
    }
    setFailure(null);
    setSending(false);
  }, [open, isProblem, initialMessage]);

  // The caret goes under the prefill once per opening, after the prefill has
  // rendered, so typing adds to it rather than landing before it.
  const caretPlaced = useRef(false);
  useEffect(() => {
    if (!open) caretPlaced.current = false;
  }, [open]);
  useEffect(() => {
    if (!open || !isProblem || caretPlaced.current) return;
    const el = textareaRef.current;
    if (!el || message !== initialMessage + "\n\n") return;
    caretPlaced.current = true;
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  }, [open, isProblem, initialMessage, message]);

  useEffect(() => {
    if (!open || isProblem) return;
    writeDraft({ rating, message });
  }, [open, isProblem, rating, message]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        close();
      }
    };
    document.addEventListener("keydown", handler, true);
    return () => document.removeEventListener("keydown", handler, true);
  }, [open, close]);

  const feedbackLabelByValue = useMemo(
    () =>
      Object.fromEntries(
        FEEDBACK_SENTIMENT_KEYS.map((item) => [item.value, t(item.labelKey)]),
      ) as Record<string, string>,
    [t, i18n.language],
  );

  const clearAndClose = useCallback(
    (toastMessage: string) => {
      setRating("");
      setMessage("");
      if (!isProblem) writeDraft({ rating: "", message: "" });
      setSending(false);
      onClose();
      toast(toastMessage);
    },
    [onClose, isProblem],
  );

  const fallbackToClipboard = useCallback(async (signal: AbortSignal) => {
    if (signal.aborted) return;
    const ratingLabel = feedbackLabelByValue[rating] ?? rating;
    const title = isProblem ? "Bristlenose problem report" : "Bristlenose feedback";
    let text = `${title} (v${health.version || "unknown"})\nRating: ${ratingLabel}\n`;
    if (message.trim()) text += `Message: ${message.trim()}\n`;
    // The send failed, so the form stays open with the draft intact and says
    // so itself (R80): a toast after closing read as success, and named
    // nowhere to paste the copy. If the copy failed too, the text exists only
    // in this form.
    let copied = false;
    if (navigator.clipboard?.writeText) {
      try {
        await navigator.clipboard.writeText(text);
        copied = true;
      } catch (err) {
        console.warn("Bristlenose feedback: clipboard write failed; keeping the form", err);
      }
    }
    if (signal.aborted) return;
    setSending(false);
    setFailure(copied ? "feedback.sendFailed" : "feedback.sendFailedNotCopied");
  }, [feedbackLabelByValue, health.version, isProblem, message, rating]);

  const submit = useCallback(async () => {
    if (!rating || sending) return;
    setSending(true);
    setFailure(null);
    const controller = new AbortController();
    inFlight.current = controller;
    const { signal } = controller;
    // `kind` only on a problem report; feedback sends no such key.
    const payload = {
      version: health.version || "unknown",
      rating,
      message: message.trim(),
      ...(isProblem ? { kind: "problem" } : {}),
    };
    const isHttp =
      window.location.protocol === "http:" || window.location.protocol === "https:";
    const url = health.feedback.url || "";
    if (url && isHttp) {
      try {
        const resp = await fetch(url, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
          signal,
        });
        // Strict success predicate: HTTP 200 + JSON body {ok: true}. A bare
        // resp.ok (any 2xx) reads a captive-portal / proxy interstitial 200
        // HTML page as "sent" and silently drops the feedback — so require the
        // server's own confirmation. Matches the native sheet + status-page form.
        const contentType = (resp.headers.get("Content-Type") ?? "").toLowerCase();
        if (resp.status === 200 && contentType.includes("application/json")) {
          const body = (await resp.json().catch(() => null)) as { ok?: unknown } | null;
          if (signal.aborted) return;
          if (body?.ok === true) {
            inFlight.current = null;
            clearAndClose(t("feedback.sent"));
            return;
          }
        }
        console.warn(
          `Bristlenose feedback: POST ${url} returned ${resp.status} without {ok:true}; falling back to clipboard`,
        );
      } catch (err) {
        if (signal.aborted) return;
        console.warn(
          `Bristlenose feedback: POST ${url} failed; falling back to clipboard`,
          err,
        );
      }
    }
    await fallbackToClipboard(signal);
    if (inFlight.current === controller) inFlight.current = null;
  }, [clearAndClose, fallbackToClipboard, health.feedback.url, health.version, isProblem, message, rating, sending]);

  return createPortal(
    // Modal backdrop. It never closes the dialog: Escape and the dialog's own buttons do (decided 24 Oct 2026).
    <div
      className={`bn-overlay feedback-overlay${open ? " visible" : ""}`}
      aria-hidden={!open}
      data-testid="bn-feedback-overlay"
    >
      <div className="bn-modal feedback-modal" data-testid="bn-feedback-modal">
        {/* Outside the boundary, so a dialog whose content crashed still has a way out with the mouse. */}
        <button className="bn-modal-close" onClick={close} aria-label={t("buttons.close")}>
          <Icon name="close" decorative />
        </button>
        <PanelErrorBoundary part>
          {() => (
            <>
              <h2>{t(isProblem ? "feedback.problemHeading" : "feedback.heading")}</h2>
              <div className="feedback-sentiments">
                {FEEDBACK_SENTIMENT_KEYS.map((item) => (
                  <button
                    key={item.value}
                    type="button"
                    className={`feedback-sentiment${rating === item.value ? " selected" : ""}`}
                    data-value={item.value}
                    onClick={() => {
                      setRating(item.value);
                      // The failure line describes the text as it was sent;
                      // an edit makes "it's on the clipboard" untrue.
                      setFailure(null);
                    }}
                  >
                    <span className="feedback-sentiment-face">{item.emoji}</span>
                    <span className="feedback-sentiment-label">{t(item.labelKey)}</span>
                  </button>
                ))}
              </div>
              <label className="feedback-label" htmlFor="bn-feedback-message">
                {t(isProblem ? "feedback.problemLabel" : "feedback.helpUsImprove")}
              </label>
              <textarea
                ref={textareaRef}
                id="bn-feedback-message"
                className="feedback-textarea"
                placeholder={t("feedback.placeholder")}
                rows={3}
                value={message}
                onChange={(e) => {
                  setMessage(e.target.value);
                  setFailure(null);
                }}
              />
              <div className="feedback-actions">
                <button
                  type="button"
                  className="feedback-btn feedback-btn-cancel"
                  onClick={close}
                >
                  {t("buttons.cancel")}
                </button>
                <button
                  type="button"
                  className="feedback-btn feedback-btn-send"
                  onClick={() => {
                    void submit();
                  }}
                  disabled={!rating || sending}
                >
                  {sending ? t("feedback.sending") : t("feedback.send")}
                </button>
              </div>
              {failure && (
                <p className="bn-export-error" role="alert">
                  {t(failure)}{" "}
                  <a
                    href={health.links.github_issues_url || DEFAULT_GITHUB_ISSUES_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {t("footer.reportIssue")}
                  </a>
                </p>
              )}
              <p className="bn-modal-footer">
                {t("feedback.anonymous")}
              </p>
            </>
          )}
        </PanelErrorBoundary>
      </div>
    </div>,
    document.body,
  );
}
