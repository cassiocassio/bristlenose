import { createRoot } from "react-dom/client";
import { VisualDiff } from "./pages/VisualDiff";

const root = document.getElementById("visual-diff-root");
if (root) {
  createRoot(root).render(<VisualDiff />);
}
