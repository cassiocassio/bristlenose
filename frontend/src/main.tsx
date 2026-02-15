import { createRoot } from "react-dom/client";
import { AboutDeveloper } from "./islands/AboutDeveloper";
import { HelloIsland } from "./islands/HelloIsland";
import { SessionsTable } from "./islands/SessionsTable";

// Mount HelloIsland (proof of concept — will be removed later)
const helloRoot = document.getElementById("bn-react-root");
if (helloRoot) {
  createRoot(helloRoot).render(<HelloIsland />);
}

// Mount SessionsTable into the sessions tab mount point
const sessionsRoot = document.getElementById("bn-sessions-table-root");
if (sessionsRoot) {
  const projectId = sessionsRoot.getAttribute("data-project-id") || "1";
  createRoot(sessionsRoot).render(<SessionsTable projectId={projectId} />);
}

// Mount AboutDeveloper into the about tab — creates its own mount point
// since the static HTML doesn't include one (serve_mode isn't passed to the
// pipeline renderer). The component silently renders nothing if /api/dev/info
// isn't available (non-dev mode).
const aboutContainer = document.querySelector(".bn-about");
if (aboutContainer) {
  const aboutDevRoot = document.createElement("div");
  aboutDevRoot.id = "bn-about-developer-root";
  aboutContainer.appendChild(aboutDevRoot);
  createRoot(aboutDevRoot).render(<AboutDeveloper />);
}
