import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditableText } from "./EditableText";

describe("EditableText", () => {
  it("renders display value when not editing", () => {
    render(<EditableText value="Hello world" onCommit={() => {}} onCancel={() => {}} />);
    expect(screen.getByText("Hello world")).toBeInTheDocument();
  });

  it("renders as span by default", () => {
    render(
      <EditableText value="text" onCommit={() => {}} onCancel={() => {}} data-testid="et" />,
    );
    expect(screen.getByTestId("et").tagName).toBe("SPAN");
  });

  it("renders as custom tag via 'as' prop", () => {
    render(
      <EditableText value="text" onCommit={() => {}} onCancel={() => {}} as="p" data-testid="et" />,
    );
    expect(screen.getByTestId("et").tagName).toBe("P");
  });

  it("applies className", () => {
    render(
      <EditableText
        value="text"
        onCommit={() => {}}
        onCancel={() => {}}
        className="quote-text"
        data-testid="et"
      />,
    );
    expect(screen.getByTestId("et")).toHaveClass("quote-text");
  });

  it("applies committed class when committed=true", () => {
    render(
      <EditableText
        value="text"
        onCommit={() => {}}
        onCancel={() => {}}
        committed={true}
        data-testid="et"
      />,
    );
    expect(screen.getByTestId("et")).toHaveClass("edited");
  });

  it("does not apply committed class when committed=false", () => {
    render(
      <EditableText
        value="text"
        onCommit={() => {}}
        onCancel={() => {}}
        committed={false}
        data-testid="et"
      />,
    );
    expect(screen.getByTestId("et")).not.toHaveClass("edited");
  });

  it("uses custom committedClassName", () => {
    render(
      <EditableText
        value="text"
        onCommit={() => {}}
        onCancel={() => {}}
        committed={true}
        committedClassName="modified"
        data-testid="et"
      />,
    );
    expect(screen.getByTestId("et")).toHaveClass("modified");
    expect(screen.getByTestId("et")).not.toHaveClass("edited");
  });

  it("sets contenteditable when isEditing=true", () => {
    render(
      <EditableText
        value="text"
        onCommit={() => {}}
        onCancel={() => {}}
        isEditing={true}
        data-testid="et"
      />,
    );
    expect(screen.getByTestId("et")).toHaveAttribute("contenteditable", "true");
  });

  it("does not set contenteditable when isEditing=false", () => {
    render(
      <EditableText
        value="text"
        onCommit={() => {}}
        onCancel={() => {}}
        isEditing={false}
        data-testid="et"
      />,
    );
    expect(screen.getByTestId("et")).not.toHaveAttribute("contenteditable");
  });

  it("focuses element when entering edit mode", () => {
    render(
      <EditableText
        value="text"
        onCommit={() => {}}
        onCancel={() => {}}
        isEditing={true}
        data-testid="et"
      />,
    );
    expect(screen.getByTestId("et")).toHaveFocus();
  });

  it("calls onCommit with new text on Enter key", () => {
    const onCommit = vi.fn();
    render(
      <EditableText
        value="original"
        onCommit={onCommit}
        onCancel={() => {}}
        isEditing={true}
        data-testid="et"
      />,
    );
    const el = screen.getByTestId("et");
    el.textContent = "updated";
    fireEvent.keyDown(el, { key: "Enter" });
    expect(onCommit).toHaveBeenCalledWith("updated");
  });

  it("calls onCancel on Escape key", () => {
    const onCancel = vi.fn();
    render(
      <EditableText
        value="original"
        onCommit={() => {}}
        onCancel={onCancel}
        isEditing={true}
        data-testid="et"
      />,
    );
    fireEvent.keyDown(screen.getByTestId("et"), { key: "Escape" });
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("calls onCommit on blur when text changed", () => {
    const onCommit = vi.fn();
    render(
      <EditableText
        value="original"
        onCommit={onCommit}
        onCancel={() => {}}
        isEditing={true}
        data-testid="et"
      />,
    );
    const el = screen.getByTestId("et");
    el.textContent = "changed";
    fireEvent.blur(el);
    expect(onCommit).toHaveBeenCalledWith("changed");
  });

  it("calls onCancel on blur when text unchanged", () => {
    const onCancel = vi.fn();
    render(
      <EditableText
        value="same"
        onCommit={() => {}}
        onCancel={onCancel}
        isEditing={true}
        data-testid="et"
      />,
    );
    const el = screen.getByTestId("et");
    // textContent was set to "same" by useEffect — leave it unchanged
    fireEvent.blur(el);
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("strips leading/trailing whitespace on commit", () => {
    const onCommit = vi.fn();
    render(
      <EditableText
        value="original"
        onCommit={onCommit}
        onCancel={() => {}}
        isEditing={true}
        data-testid="et"
      />,
    );
    const el = screen.getByTestId("et");
    el.textContent = "  updated  ";
    fireEvent.keyDown(el, { key: "Enter" });
    expect(onCommit).toHaveBeenCalledWith("updated");
  });

  it("forwards data-testid", () => {
    render(
      <EditableText value="x" onCommit={() => {}} onCancel={() => {}} data-testid="my-et" />,
    );
    expect(screen.getByTestId("my-et")).toBeInTheDocument();
  });

  it("forwards data-edit-key", () => {
    render(
      <EditableText
        value="x"
        onCommit={() => {}}
        onCancel={() => {}}
        data-edit-key="section-1"
        data-testid="et"
      />,
    );
    expect(screen.getByTestId("et")).toHaveAttribute("data-edit-key", "section-1");
  });

  // Click-to-edit trigger mode
  it("enters edit mode on click when trigger='click'", async () => {
    render(
      <EditableText
        value="clickable"
        onCommit={() => {}}
        onCancel={() => {}}
        trigger="click"
        data-testid="et"
      />,
    );
    const el = screen.getByTestId("et");
    expect(el).not.toHaveAttribute("contenteditable");
    await userEvent.click(el);
    expect(el).toHaveAttribute("contenteditable", "true");
  });

  it("does not enter edit mode on click when trigger='external'", async () => {
    render(
      <EditableText
        value="external"
        onCommit={() => {}}
        onCancel={() => {}}
        trigger="external"
        data-testid="et"
      />,
    );
    const el = screen.getByTestId("et");
    await userEvent.click(el);
    expect(el).not.toHaveAttribute("contenteditable");
  });
});
