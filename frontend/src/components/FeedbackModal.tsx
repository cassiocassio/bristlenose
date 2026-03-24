import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { useInert } from "../hooks/useInert";
import { toast } from "../utils/toast";
import type { HealthResponse } from "../utils/health";

interface FeedbackModalProps {
  open: boolean;
  onClose: () => void;
  health: HealthResponse;
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
  }
}

export function FeedbackModal({ open, onClose, health }: FeedbackModalProps) {
  const { t } = useTranslation();
  useInert(open);
  const [rating, setRating] = useState("");
  const [message, setMessage] = useState("");
  const [sending, setSending] = useState(false);

  useEffect(() => {
    if (!open) return;
    const draft = readDraft();
    setRating(draft.rating);
    setMessage(draft.message);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    writeDraft({ rating, message });
  }, [open, rating, message]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", handler, true);
    return () => document.removeEventListener("keydown", handler, true);
  }, [open, onClose]);

  const feedbackLabelByValue = useMemo(
    () =>
      Object.fromEntries(
        FEEDBACK_SENTIMENT_KEYS.map((item) => [item.value, t(item.labelKey)]),
      ) as Record<string, string>,
    [t],
  );

  const clearAndClose = useCallback(
    (toastMessage: string) => {
      setRating("");
      setMessage("");
      writeDraft({ rating: "", message: "" });
      setSending(false);
      onClose();
      toast(toastMessage);
    },
    [onClose],
  );

  const fallbackToClipboard = useCallback(async () => {
    const ratingLabel = feedbackLabelByValue[rating] ?? rating;
    let text = `Bristlenose feedback (v${health.version || "unknown"})\nRating: ${ratingLabel}\n`;
    if (message.trim()) text += `Message: ${message.trim()}\n`;
    if (!navigator.clipboard?.writeText) {
      clearAndClose(t("feedback.copyFailed"));
      return;
    }
    try {
      await navigator.clipboard.writeText(text);
      clearAndClose(t("feedback.copiedToClipboard"));
    } catch {
      clearAndClose(t("feedback.copyFailed"));
    }
  }, [clearAndClose, feedbackLabelByValue, health.version, message, rating]);

  const submit = useCallback(async () => {
    if (!rating || sending) return;
    setSending(true);
    const payload = {
      version: health.version || "unknown",
      rating,
      message: message.trim(),
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
        });
        if (resp.ok) {
          clearAndClose(t("feedback.sent"));
          return;
        }
      } catch {
      }
    }
    await fallbackToClipboard();
  }, [clearAndClose, fallbackToClipboard, health.feedback.url, health.version, message, rating, sending]);

  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose],
  );

  return createPortal(
    <div
      className={`bn-overlay feedback-overlay${open ? " visible" : ""}`}
      onClick={handleOverlayClick}
      aria-hidden={!open}
      data-testid="bn-feedback-overlay"
    >
      <div className="bn-modal feedback-modal" data-testid="bn-feedback-modal">
        <h2>{t("feedback.heading")}</h2>
        <div className="feedback-sentiments">
          {FEEDBACK_SENTIMENT_KEYS.map((item) => (
            <button
              key={item.value}
              type="button"
              className={`feedback-sentiment${rating === item.value ? " selected" : ""}`}
              data-value={item.value}
              onClick={() => setRating(item.value)}
            >
              <span className="feedback-sentiment-face">{item.emoji}</span>
              <span className="feedback-sentiment-label">{t(item.labelKey)}</span>
            </button>
          ))}
        </div>
        <label className="feedback-label" htmlFor="bn-feedback-message">
          {t("feedback.helpUsImprove")}
        </label>
        <textarea
          id="bn-feedback-message"
          className="feedback-textarea"
          placeholder={t("feedback.placeholder")}
          rows={3}
          value={message}
          onChange={(e) => setMessage(e.target.value)}
        />
        <div className="feedback-actions">
          <button
            type="button"
            className="feedback-btn feedback-btn-cancel"
            onClick={onClose}
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
        <p className="bn-modal-footer">
          {t("feedback.anonymous")}
        </p>
      </div>
    </div>,
    document.body,
  );
}
