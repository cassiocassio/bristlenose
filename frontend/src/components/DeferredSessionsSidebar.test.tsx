import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PanelErrorBoundary } from "./PanelErrorBoundary";

beforeEach(() => {
  vi.resetModules();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.doUnmock("./SessionsSidebar");
});

it("contains a failed download and retries from the sidebar's existing button", async () => {
  const log = vi.spyOn(console, "error").mockImplementation(() => {});
  vi.doMock("./SessionsSidebar", () => { throw new Error("download failed"); });
  const { DeferredSessionsSidebar } = await import("./DeferredSessionsSidebar");
  render(<><PanelErrorBoundary><DeferredSessionsSidebar visible /></PanelErrorBoundary><main>Transcript</main></>);
  const retry = await screen.findByRole("button", { name: "Retry" });
  expect(screen.getByText("Transcript")).toBeVisible();
  vi.doMock("./SessionsSidebar", () => ({ SessionsSidebar: () => <nav>Recovered list</nav> }));
  fireEvent.click(retry);
  await screen.findByText("Recovered list");
  log.mockRestore();
});

it("does not fetch a closed panel, and loads as soon as it opens", async () => {
  const load = vi.fn(() => ({ SessionsSidebar: () => <nav>Session list</nav> }));
  vi.doMock("./SessionsSidebar", load);
  const { DeferredSessionsSidebar } = await import("./DeferredSessionsSidebar");
  const { rerender } = render(<DeferredSessionsSidebar visible={false} />);
  expect(load).not.toHaveBeenCalled();
  rerender(<DeferredSessionsSidebar visible />);
  await screen.findByText("Session list");
  expect(load).toHaveBeenCalledTimes(1);
});

it("an open panel loading never suspends the main report", async () => {
  let finish!: (value: { SessionsSidebar: () => React.JSX.Element }) => void;
  vi.doMock("./SessionsSidebar", () => new Promise((resolve) => { finish = resolve; }));
  const { DeferredSessionsSidebar } = await import("./DeferredSessionsSidebar");
  render(<><DeferredSessionsSidebar visible /><main>Transcript</main></>);
  expect(screen.getByText("Transcript")).toBeVisible();
  await waitFor(() => expect(finish).toBeDefined());
  await act(async () => finish({ SessionsSidebar: () => <nav>Session list</nav> }));
  await screen.findByText("Session list");
});

it("preloads after a frame and idle time, sharing the result with an early open", async () => {
  const load = vi.fn(() => ({ SessionsSidebar: () => <nav>Session list</nav> }));
  vi.doMock("./SessionsSidebar", load);
  let frame!: FrameRequestCallback;
  let idle!: IdleRequestCallback;
  vi.stubGlobal("requestAnimationFrame", vi.fn((callback) => { frame = callback; return 1; }));
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
  vi.stubGlobal("requestIdleCallback", vi.fn((callback) => { idle = callback; return 2; }));
  vi.stubGlobal("cancelIdleCallback", vi.fn());
  const { DeferredSessionsSidebar, PreloadSessionsSidebar } = await import("./DeferredSessionsSidebar");
  const { rerender } = render(<><PreloadSessionsSidebar /><DeferredSessionsSidebar visible={false} /></>);
  expect(load).not.toHaveBeenCalled();
  act(() => frame(0));
  expect(load).not.toHaveBeenCalled();
  await act(async () => idle({ didTimeout: false, timeRemaining: () => 10 }));
  expect(load).toHaveBeenCalledTimes(1);
  rerender(<><PreloadSessionsSidebar /><DeferredSessionsSidebar visible /></>);
  await screen.findByText("Session list");
  expect(load).toHaveBeenCalledTimes(1);
});

it("cancels a scheduled preload when leaving the lens", async () => {
  let frame!: FrameRequestCallback;
  const cancelIdle = vi.fn();
  vi.stubGlobal("requestAnimationFrame", vi.fn((callback) => { frame = callback; return 1; }));
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
  vi.stubGlobal("requestIdleCallback", vi.fn(() => 2));
  vi.stubGlobal("cancelIdleCallback", cancelIdle);
  const { PreloadSessionsSidebar } = await import("./DeferredSessionsSidebar");
  const view = render(<PreloadSessionsSidebar />);
  act(() => frame(0));
  view.unmount();
  expect(cancelIdle).toHaveBeenCalledWith(2);
});

it("preloads without requestIdleCallback and cancels its fallback on unmount", async () => {
  const load = vi.fn(() => ({ SessionsSidebar: () => <nav>Session list</nav> }));
  vi.doMock("./SessionsSidebar", load);
  vi.stubGlobal("requestIdleCallback", undefined);
  const { PreloadSessionsSidebar } = await import("./DeferredSessionsSidebar");
  vi.useFakeTimers();
  const first = render(<PreloadSessionsSidebar />);
  act(() => vi.advanceTimersByTime(100));
  expect(load).not.toHaveBeenCalled();
  first.unmount();
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  expect(load).not.toHaveBeenCalled();
  render(<PreloadSessionsSidebar />);
  await act(async () => vi.advanceTimersByTimeAsync(2000));
  expect(load).toHaveBeenCalledTimes(1);
});
