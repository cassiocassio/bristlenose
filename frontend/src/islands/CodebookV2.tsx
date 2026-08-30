/**
 * Codebook v2 — Phase 0: the seam.
 *
 * Deliberately empty. Phase 0 exists to prove the route, the lazy chunk and the
 * mount before any design content is written, because the alternative — start
 * with a component — has nowhere to live and becomes a rewrite in place by
 * accident. See `docs/design-codebook-v2-plan.md`.
 *
 * Phases, in order: 0 seam · 1 data · 2 rail · 3 codebook page · 4 browse grid ·
 * 5 destructive edges · 6 parity and deletion.
 */

interface Props {
  projectId: string;
  refreshKey?: number;
  projectName?: string;
}

export function CodebookV2({ projectId, projectName }: Props) {
  return (
    <div className="contentinner" data-testid="bn-codebook-v2">
      <section>
        {/* The zone-title row and its datum — `.section-heading` lifted whole,
            including the first-child margin-top:0 that aligns every lens's
            title to the same line. Definitive per the fidelity map. */}
        <div className="section-heading">
          <h1>Codebook</h1>
        </div>
        <p className="pg-stat">
          Phase 0 — the seam. Project {projectName ?? projectId}.
        </p>
      </section>
    </div>
  );
}
