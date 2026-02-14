import { createRoot } from "react-dom/client";
import { HelloIsland } from "./islands/HelloIsland";

const root = document.getElementById("bn-react-root");
if (root) {
  createRoot(root).render(<HelloIsland />);
}
