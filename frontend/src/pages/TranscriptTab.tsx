import { useParams } from "react-router-dom";
import { TranscriptPage } from "../islands/TranscriptPage";
import { useProjectId } from "../hooks/useProjectId";

export function TranscriptTab() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const projectId = useProjectId();
  return <TranscriptPage projectId={projectId} sessionId={sessionId ?? ""} />;
}
