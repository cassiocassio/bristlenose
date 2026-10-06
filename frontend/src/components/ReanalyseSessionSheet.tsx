/**
 * Re-analyse one session after a speaker recode (design-people.md §J7 R3).
 *
 * A recode into or out of participant is free and instant, but it leaves the
 * session without the right quotes: they were extracted from the wrong speaker.
 * Getting them is a paid run, so it is the researcher's act, and this sheet
 * says what it costs and what it changes before they take it — the house rule
 * from the re-analyse and uninstall sheets: counted, plain consequences, Cancel
 * leading, the act trailing and taking the default.
 *
 * Confirming pins the speakers through serve. In the Mac app it then asks the
 * app to run the analysis; in a browser there is no runner, so it shows the
 * command that runs it.
 */

import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { postProjectAction } from "../shims/bridge";
import { getReanalyse, postReanalyse, type ReanalyseInfo } from "../utils/api";
import { isEmbedded } from "../utils/embedded";

interface Props {
  sessionId: string;
  /** "#3", as the grid shows the session. */
  sessionLabel: string;
  onClose: () => void;
  /** The pins are written: the grid re-reads. */
  onPinned: () => void;
}

type Step = "confirm" | "command" | "failed";

export function ReanalyseSessionSheet({ sessionId, sessionLabel, onClose, onPinned }: Props) {
  const { t, i18n } = useTranslation();
  const [info, setInfo] = useState<ReanalyseInfo | null>(null);
  const [step, setStep] = useState<Step>("confirm");
  const [command, setCommand] = useState("");
  const [busy, setBusy] = useState(false);
  const confirmRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let live = true;
    getReanalyse(sessionId)
      .then((got) => live && setInfo(got))
      .catch(() => live && setStep("failed"));
    return () => {
      live = false;
    };
  }, [sessionId]);

  useEffect(() => {
    confirmRef.current?.focus();
  }, [info, step]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const confirm = () => {
    if (busy || !info || info.running) return;
    setBusy(true);
    postReanalyse(sessionId)
      .then((res) => {
        onPinned();
        if (isEmbedded()) {
          postProjectAction("reanalyse-session", { sessionId });
          onClose();
        } else {
          setCommand(res.command);
          setStep("command");
        }
      })
      .catch(() => setStep("failed"))
      .finally(() => setBusy(false));
  };

  const cost =
    info?.cost_usd != null
      ? new Intl.NumberFormat(i18n.language, { style: "currency", currency: "USD" }).format(info.cost_usd)
      : null;

  const copy = () => {
    void navigator.clipboard?.writeText(command).catch(() => undefined);
  };

  return (
    <div className="bn-overlay visible" data-testid="bn-reanalyse-sheet">
      <div className="bn-modal" role="dialog" aria-modal="true" aria-labelledby="bn-reanalyse-title">
        <h2 id="bn-reanalyse-title">{t("sessions.reanalyse.title", { session: sessionLabel })}</h2>
        {step === "failed" ? (
          <p>{t("sessions.reanalyse.failed")}</p>
        ) : step === "command" ? (
          <>
            <p>{t("sessions.reanalyse.runIt")}</p>
            <pre data-testid="bn-reanalyse-command">{command}</pre>
          </>
        ) : info?.running ? (
          <p>{t("sessions.reanalyse.running")}</p>
        ) : (
          <>
            <p>{t("sessions.reanalyse.what")}</p>
            <p>{t("sessions.reanalyse.kept")}</p>
            {cost && <p data-testid="bn-reanalyse-cost">{t("sessions.reanalyse.cost", { cost })}</p>}
          </>
        )}
        <div className="bn-modal-actions">
          {step === "command" ? (
            <>
              <button className="bn-btn bn-btn-cancel" onClick={copy}>
                {t("buttons.copy")}
              </button>
              <button className="bn-btn bn-btn-primary" onClick={onClose} ref={confirmRef}>
                {t("buttons.ok")}
              </button>
            </>
          ) : step === "failed" || info?.running ? (
            <button className="bn-btn bn-btn-primary" onClick={onClose} ref={confirmRef}>
              {t("buttons.ok")}
            </button>
          ) : (
            <>
              <button className="bn-btn bn-btn-cancel" onClick={onClose}>
                {t("buttons.cancel")}
              </button>
              <button
                className="bn-btn bn-btn-primary"
                onClick={confirm}
                disabled={!info || busy}
                ref={confirmRef}
                data-testid="bn-reanalyse-confirm"
              >
                {t("sessions.reanalyse.confirm")}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
