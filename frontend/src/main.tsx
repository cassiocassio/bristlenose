import { createRoot } from "react-dom/client";
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
