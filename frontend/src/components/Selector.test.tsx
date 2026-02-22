import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Selector } from "./Selector";

interface FruitItem {
  id: string;
  name: string;
  colour: string;
}

const fruits: FruitItem[] = [
  { id: "apple", name: "Apple", colour: "red" },
  { id: "banana", name: "Banana", colour: "yellow" },
  { id: "cherry", name: "Cherry", colour: "red" },
];

describe("Selector", () => {
  it("renders the trigger button with label and caret", () => {
    render(
      <Selector
        label="Pick fruit"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        data-testid="sel"
      />,
    );
    const trigger = screen.getByRole("button", { name: /Pick fruit/i });
    expect(trigger).toBeTruthy();
    expect(trigger.querySelector(".bn-selector__caret")).toBeTruthy();
  });

  it("dropdown is closed by default", () => {
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        data-testid="sel"
      />,
    );
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("opens dropdown on trigger click", () => {
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        data-testid="sel"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pick/i }));
    expect(screen.getByRole("listbox")).toBeTruthy();
    expect(screen.getAllByRole("option")).toHaveLength(3);
  });

  it("renders item content via renderItem", () => {
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span data-testid={`item-${f.id}`}>{f.name} ({f.colour})</span>}
        data-testid="sel"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pick/i }));
    expect(screen.getByTestId("item-apple").textContent).toBe("Apple (red)");
    expect(screen.getByTestId("item-banana").textContent).toBe("Banana (yellow)");
  });

  it("marks active item with aria-selected and active class", () => {
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        activeKey="banana"
        data-testid="sel"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pick/i }));
    const options = screen.getAllByRole("option");
    expect(options[0].getAttribute("aria-selected")).toBe("false");
    expect(options[1].getAttribute("aria-selected")).toBe("true");
    expect(options[2].getAttribute("aria-selected")).toBe("false");
    // Active class on the button/anchor inside
    const activeBtn = options[1].querySelector(".bn-selector__item--active");
    expect(activeBtn).toBeTruthy();
  });

  it("calls onSelect and closes dropdown on item click", () => {
    const onSelect = vi.fn();
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        onSelect={onSelect}
        data-testid="sel"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pick/i }));
    expect(screen.getByRole("listbox")).toBeTruthy();
    // Click the second item (Banana)
    const buttons = screen.getByRole("listbox").querySelectorAll("button");
    fireEvent.click(buttons[1]);
    expect(onSelect).toHaveBeenCalledWith(fruits[1]);
    // Dropdown should be closed
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("renders anchors when itemHref is provided", () => {
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        itemHref={(f) => `/fruit/${f.id}`}
        data-testid="sel"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pick/i }));
    const links = screen.getByRole("listbox").querySelectorAll("a");
    expect(links).toHaveLength(3);
    expect(links[0].getAttribute("href")).toBe("/fruit/apple");
    expect(links[1].getAttribute("href")).toBe("/fruit/banana");
    expect(links[2].getAttribute("href")).toBe("/fruit/cherry");
  });

  it("closes dropdown on Escape key", () => {
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        data-testid="sel"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pick/i }));
    expect(screen.getByRole("listbox")).toBeTruthy();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("closes dropdown on outside click", () => {
    render(
      <div>
        <Selector
          label="Pick"
          items={fruits}
          itemKey={(f) => f.id}
          renderItem={(f) => <span>{f.name}</span>}
          data-testid="sel"
        />
        <button data-testid="outside">Outside</button>
      </div>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pick/i }));
    expect(screen.getByRole("listbox")).toBeTruthy();
    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("toggles dropdown on repeated trigger clicks", () => {
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        data-testid="sel"
      />,
    );
    const trigger = screen.getByRole("button", { name: /Pick/i });
    fireEvent.click(trigger);
    expect(screen.getByRole("listbox")).toBeTruthy();
    fireEvent.click(trigger);
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("sets aria-expanded on trigger", () => {
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        data-testid="sel"
      />,
    );
    const trigger = screen.getByRole("button", { name: /Pick/i });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(trigger);
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
  });

  it("applies custom className", () => {
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        className="my-custom"
        data-testid="sel"
      />,
    );
    const container = screen.getByTestId("sel");
    expect(container.classList.contains("bn-selector")).toBe(true);
    expect(container.classList.contains("my-custom")).toBe(true);
  });

  it("renders buttons (not anchors) when no itemHref", () => {
    render(
      <Selector
        label="Pick"
        items={fruits}
        itemKey={(f) => f.id}
        renderItem={(f) => <span>{f.name}</span>}
        data-testid="sel"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pick/i }));
    const listbox = screen.getByRole("listbox");
    expect(listbox.querySelectorAll("button")).toHaveLength(3);
    expect(listbox.querySelectorAll("a")).toHaveLength(0);
  });

  it("handles empty items array", () => {
    render(
      <Selector
        label="Pick"
        items={[]}
        itemKey={(f: FruitItem) => f.id}
        renderItem={(f: FruitItem) => <span>{f.name}</span>}
        data-testid="sel"
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Pick/i }));
    const listbox = screen.getByRole("listbox");
    expect(listbox.querySelectorAll("li")).toHaveLength(0);
  });
});
