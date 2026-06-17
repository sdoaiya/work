export function DesktopDock() {
  return (
    <main className="dock-shell">
      <button className="floating-ball" aria-label="打开 AI WorkDock">
        AI
      </button>
      <section className="dock-panel" aria-label="AI WorkDock 主面板">
        <h1>AI WorkDock</h1>
        <input placeholder="搜索 Prompt、知识卡、Skill" />
        <button>复制 Prompt</button>
        <p>未登录时显示登录入口，登录后同步团队 Prompt 与 Skill。</p>
      </section>
    </main>
  );
}
