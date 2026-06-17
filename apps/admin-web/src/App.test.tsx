import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { App } from "./App";

describe("AI WorkDock admin web", () => {
  it("renders the login page", () => {
    render(<App initialView="login" />);

    expect(screen.getByRole("heading", { name: "AI WorkDock" })).toBeInTheDocument();
    expect(screen.getByLabelText("邮箱")).toBeInTheDocument();
    expect(screen.getByLabelText("密码")).toBeInTheDocument();
  });

  it("shows a login error", async () => {
    render(<App initialView="login" />);

    await userEvent.click(screen.getByRole("button", { name: "登录" }));

    expect(screen.getByText("请输入邮箱和密码")).toBeInTheDocument();
  });

  it("renders and filters prompts", async () => {
    render(<App initialView="prompts" />);

    expect(screen.getByText("政府汇报材料")).toBeInTheDocument();
    await userEvent.type(screen.getByPlaceholderText("搜索 Prompt"), "Codex");

    expect(screen.getByText("Codex 调试助手")).toBeInTheDocument();
    expect(screen.queryByText("政府汇报材料")).not.toBeInTheDocument();
  });

  it("shows copy success for prompts", async () => {
    render(<App initialView="prompts" />);

    await userEvent.click(screen.getAllByRole("button", { name: "复制" })[0]);

    expect(screen.getByText("复制成功")).toBeInTheDocument();
  });

  it("renders skill list and admin review action", () => {
    render(<App initialView="skills" role="admin" />);

    expect(screen.getByText("G端政府汇报方案 Skill")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "审核通过" })).toBeInTheDocument();
  });

  it("hides skill review action from members", () => {
    render(<App initialView="skills" role="member" />);

    expect(screen.queryByRole("button", { name: "审核通过" })).not.toBeInTheDocument();
  });
});
