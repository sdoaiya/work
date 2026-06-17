import { useMemo, useState } from "react";
import "./styles.css";

type View = "login" | "prompts" | "skills";
type Role = "admin" | "member";

type AppProps = {
  initialView?: View;
  role?: Role;
};

const prompts = [
  {
    id: "prompt-gov",
    title: "政府汇报材料",
    description: "把口语化业务思路整理成政府汇报方案",
    tags: ["政府汇报", "方案"]
  },
  {
    id: "prompt-codex",
    title: "Codex 调试助手",
    description: "定位测试失败并输出最小修复方案",
    tags: ["Codex", "开发"]
  }
];

const skills = [
  {
    id: "skill-gov",
    name: "G端政府汇报方案 Skill",
    version: "1.0.0",
    risk: "low",
    status: "pending"
  }
];

export function App({ initialView = "login", role = "admin" }: AppProps) {
  const [view, setView] = useState<View>(initialView);
  const [query, setQuery] = useState("");
  const [loginError, setLoginError] = useState("");
  const [copyMessage, setCopyMessage] = useState("");

  const filteredPrompts = useMemo(() => {
    const value = query.trim().toLowerCase();
    if (!value) return prompts;
    return prompts.filter((prompt) =>
      [prompt.title, prompt.description, prompt.tags.join(" ")]
        .join(" ")
        .toLowerCase()
        .includes(value)
    );
  }, [query]);

  function submitLogin(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    if (!form.get("email") || !form.get("password")) {
      setLoginError("请输入邮箱和密码");
      return;
    }
    setLoginError("");
    setView("prompts");
  }

  return (
    <main className="shell">
      <aside className="sidebar" aria-label="主导航">
        <div className="brand">AI WorkDock</div>
        <button
          aria-label="打开登录页"
          className={view === "login" ? "active" : ""}
          onClick={() => setView("login")}
        >
          登录
        </button>
        <button className={view === "prompts" ? "active" : ""} onClick={() => setView("prompts")}>
          Prompt
        </button>
        <button className={view === "skills" ? "active" : ""} onClick={() => setView("skills")}>
          Skill
        </button>
      </aside>

      <section className="content">
        {view === "login" && (
          <form className="panel" onSubmit={submitLogin}>
            <h1>AI WorkDock</h1>
            <label>
              邮箱
              <input name="email" type="email" />
            </label>
            <label>
              密码
              <input name="password" type="password" />
            </label>
            <button type="submit">登录</button>
            {loginError && <p className="error">{loginError}</p>}
          </form>
        )}

        {view === "prompts" && (
          <div className="stack">
            <header className="toolbar">
              <h1>Prompt 库</h1>
              <input
                placeholder="搜索 Prompt"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
              />
            </header>
            <div className="grid">
              {filteredPrompts.map((prompt) => (
                <article className="item" key={prompt.id}>
                  <h2>{prompt.title}</h2>
                  <p>{prompt.description}</p>
                  <div className="tags">{prompt.tags.join(" / ")}</div>
                  <button onClick={() => setCopyMessage("复制成功")}>复制</button>
                </article>
              ))}
            </div>
            {copyMessage && <p className="success">{copyMessage}</p>}
          </div>
        )}

        {view === "skills" && (
          <div className="stack">
            <header className="toolbar">
              <h1>Team Skill Center</h1>
              <button>上传 Skill</button>
            </header>
            <div className="grid">
              {skills.map((skill) => (
                <article className="item" key={skill.id}>
                  <h2>{skill.name}</h2>
                  <p>版本 {skill.version} · 风险 {skill.risk} · 状态 {skill.status}</p>
                  {role === "admin" && <button>审核通过</button>}
                </article>
              ))}
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
