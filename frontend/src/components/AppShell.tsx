import { useState } from "react";
import { Outlet } from "react-router-dom";
import { LeftNav } from "./LeftNav";
import { TopBar } from "./TopBar";
import { useApi } from "../api/useApi";
import { api } from "../api/client";

// Per-viewer convenience only (PID-002 shell refinement §2) — not an
// account/server preference. localStorage can throw (private browsing,
// blocked storage) or simply be unavailable, so every access is wrapped
// and falls back to the default expanded state.
const NAV_COLLAPSE_KEY = "arena.leftNav.collapsed";

function readStoredCollapsed(): boolean {
  try {
    return window.localStorage.getItem(NAV_COLLAPSE_KEY) === "1";
  } catch {
    return false;
  }
}

function writeStoredCollapsed(value: boolean): void {
  try {
    window.localStorage.setItem(NAV_COLLAPSE_KEY, value ? "1" : "0");
  } catch {
    // Best-effort only — the collapse toggle still works for this session.
  }
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(readStoredCollapsed);
  const build = useApi(api.buildinfo, []);
  const ready = useApi(api.ready, []);

  function toggleCollapsed() {
    setCollapsed((c) => {
      const next = !c;
      writeStoredCollapsed(next);
      return next;
    });
  }

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
        <LeftNav collapsed={collapsed} onToggle={toggleCollapsed} />
        <main id="main-content" className="app-shell__main" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
