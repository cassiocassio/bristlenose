/**
 * The re-analyse sheet (design-people.md §J7 R3): it says what the paid run
 * changes and costs, writes the pins only on confirm, and then either asks the
 * Mac to run it or, in a browser, shows the command that does.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { ReanalyseSessionSheet } from "./ReanalyseSessionSheet";
import { getReanalyse, postReanalyse } from "../utils/api";
import { postProjectAction } from "../shims/bridge";
import { isEmbedded } from "../utils/embedded";

vi.mock("../utils/api", () => ({ getReanalyse: vi.fn(), postReanalyse: vi.fn() }));
vi.mock("../shims/bridge", () => ({ postProjectAction: vi.fn() }));
vi.mock("../utils/embedded", () => ({ isEmbedded: vi.fn(() => false) }));

const info = { needed: true, cost_usd: 0.12, running: false, command: "bristlenose run '/x y'" };

beforeEach(() => {
  vi.mocked(getReanalyse).mockReset().mockResolvedValue(info);
  vi.mocked(postReanalyse).mockReset().mockResolvedValue({ pinned: 2, command: info.command });
  vi.mocked(postProjectAction).mockReset();
  vi.mocked(isEmbedded).mockReturnValue(false);
});

afterEach(() => vi.clearAllMocks());

const renderSheet = (props: Partial<Parameters<typeof ReanalyseSessionSheet>[0]> = {}) =>
  render(<ReanalyseSessionSheet sessionId="s3" sessionLabel="#3" onClose={vi.fn()} onPinned={vi.fn()} {...props} />);

describe("ReanalyseSessionSheet", () => {
  it("says what it changes and what it costs, and writes nothing until confirmed", async () => {
    renderSheet();
    await screen.findByTestId("bn-reanalyse-cost");
    expect(screen.getByText(/whole study/)).toBeInTheDocument();
    expect(screen.getByTestId("bn-reanalyse-cost").textContent).toContain("0.12");
    expect(postReanalyse).not.toHaveBeenCalled();
  });

  it("Cancel writes nothing", async () => {
    const onClose = vi.fn();
    renderSheet({ onClose });
    await screen.findByTestId("bn-reanalyse-cost");
    fireEvent.click(screen.getByText("Cancel"));
    expect(onClose).toHaveBeenCalled();
    expect(postReanalyse).not.toHaveBeenCalled();
  });

  it("in a browser, confirming pins the speakers and shows the command", async () => {
    const onPinned = vi.fn();
    renderSheet({ onPinned });
    await screen.findByTestId("bn-reanalyse-cost");
    fireEvent.click(screen.getByTestId("bn-reanalyse-confirm"));
    expect(await screen.findByTestId("bn-reanalyse-command")).toHaveTextContent("bristlenose run '/x y'");
    expect(postReanalyse).toHaveBeenCalledWith("s3");
    expect(onPinned).toHaveBeenCalled();
    expect(postProjectAction).not.toHaveBeenCalled();
  });

  it("in the Mac app, confirming asks the app to run it and closes", async () => {
    vi.mocked(isEmbedded).mockReturnValue(true);
    const onClose = vi.fn();
    renderSheet({ onClose });
    await screen.findByTestId("bn-reanalyse-cost");
    fireEvent.click(screen.getByTestId("bn-reanalyse-confirm"));
    await waitFor(() => expect(postProjectAction).toHaveBeenCalledWith("reanalyse-session", { sessionId: "s3" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("while a run owns the project it offers nothing to confirm", async () => {
    vi.mocked(getReanalyse).mockResolvedValue({ ...info, running: true });
    renderSheet();
    await screen.findByText(/already running/);
    expect(screen.queryByTestId("bn-reanalyse-confirm")).toBeNull();
  });
});
