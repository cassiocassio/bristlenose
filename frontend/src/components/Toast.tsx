/**
 * Toast — minimal notification component.
 *
 * Portal-rendered to document.body. Auto-dismisses after 2 seconds.
 * Only one toast visible at a time (new calls replace the current).
 * Reuses atoms/toast.css (.clipboard-toast).
 */

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

interface ToastProps {
  message: string;
  onDismiss: () => void;
  duration?: number;
}

export function Toast({ message, onDismiss, duration = 2000 }: ToastProps) {
  const [visible, setVisible] = useState(false);

  // Trigger fade-in on mount
  useEffect(() => {
    // Force reflow before adding .show (matches vanilla pattern)
    const raf = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(raf);
  }, []);

  // Auto-dismiss
  useEffect(() => {
    const timer = setTimeout(() => {
      setVisible(false);
      // Wait for fade-out transition before unmounting
      setTimeout(onDismiss, 300);
    }, duration);
    return () => clearTimeout(timer);
  }, [duration, onDismiss]);

  return createPortal(
    <div
      className={`clipboard-toast${visible ? " show" : ""}`}
      data-testid="bn-toast"
    >
      {message}
    </div>,
    document.body,
  );
}
