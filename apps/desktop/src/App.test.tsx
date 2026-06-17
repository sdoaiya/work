import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DesktopDock } from "./App";

describe("AI WorkDock desktop shell", () => {
  it("shows the floating ball", () => {
    render(<DesktopDock />);

    expect(screen.getByRole("button", { name: "打开 AI WorkDock" })).toBeInTheDocument();
  });

  it("shows the main panel search and copy actions", () => {
    render(<DesktopDock />);

    expect(screen.getByLabelText("AI WorkDock 主面板")).toBeInTheDocument();
    expect(screen.getByPlaceholderText("搜索 Prompt、知识卡、Skill")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "复制 Prompt" })).toBeInTheDocument();
  });
});
