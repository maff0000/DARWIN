import { useState } from "react";
import { Outlet } from "react-router-dom";
import { LeftNav } from "./LeftNav";
import { TopBar } from "./TopBar";
import { useApi } from "../api/useApi";
import { api } from "../api/client";

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const build = useApi(api.buildinfo, []);
  const ready = useApi(api.ready, []);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <TopBar
        build={build.status === "ready" ? build.data : undefined}
        readiness={ready.status === "ready" ? ready.data : undefined}
        loadFailed={build.status === "error" && ready.status === "error"}
      />
      <div className="app-shell__body">
        <LeftNav collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)} />
        <main id="main-content" className="app-shell__main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
