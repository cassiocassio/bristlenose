import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders text for readonly variant", () => {
    render(<Badge text="frustration" variant="readonly" />);
    expect(screen.getByText("frustration")).toBeInTheDocument();
  });

  it("renders text for ai variant", () => {
    render(<Badge text="delight" variant="ai" />);
    expect(screen.getByText("delight")).toBeInTheDocument();
  });

  it("renders text for user variant", () => {
    render(<Badge text="my-tag" variant="user" />);
    expect(screen.getByText("my-tag")).toBeInTheDocument();
  });

  it("ai badge: click fires onDelete", async () => {
    const onDelete = vi.fn();
    render(<Badge text="delight" variant="ai" onDelete={onDelete} />);
    await userEvent.click(screen.getByText("delight"));
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("user badge: x button appears and click fires onDelete", async () => {
    const onDelete = vi.fn();
    render(<Badge text="my-tag" variant="user" onDelete={onDelete} />);
    const btn = screen.getByRole("button", { name: /remove my-tag/i });
    expect(btn).toBeInTheDocument();
    await userEvent.click(btn);
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("readonly: no delete affordance", () => {
    const onDelete = vi.fn();
    render(<Badge text="info" variant="readonly" onDelete={onDelete} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("applies sentiment class", () => {
    render(<Badge text="test" variant="readonly" sentiment="frustration" data-testid="b" />);
    expect(screen.getByTestId("b")).toHaveClass("badge-frustration");
  });

  it("forwards data-testid", () => {
    render(<Badge text="x" variant="readonly" data-testid="my-badge" />);
    expect(screen.getByTestId("my-badge")).toBeInTheDocument();
  });
});
