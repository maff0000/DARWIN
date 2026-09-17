import { NavLink } from "react-router-dom";
import { NAV } from "../nav";

export function LeftNav({ collapsed, onToggle }: { collapsed: boolean; onToggle: () => void }) {
  return (
    <nav className={`left-nav ${collapsed ? "left-nav--collapsed" : ""}`} aria-label="Primary">
      <button
        type="button"
        className="left-nav__toggle"
        onClick={onToggle}
        aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
        aria-expanded={!collapsed}
      >
        <span aria-hidden="true">{collapsed ? "»" : "«"}</span>
      </button>
      <div className="left-nav__scroll">
        {NAV.map((group) => (
          <div className="left-nav__group" key={group.label}>
            {!collapsed && <div className="left-nav__group-label">{group.label}</div>}
            <ul>
              {group.items.map((item) => (
                <li key={item.path}>
                  <NavLink
                    to={item.path}
                    end={item.path === "/"}
                    className={({ isActive }) =>
                      `left-nav__link ${isActive ? "left-nav__link--active" : ""}`
                    }
                  >
                    <span className="left-nav__dot" aria-hidden="true" />
                    {!collapsed && <span>{item.label}</span>}
                    {collapsed && <span className="visually-hidden">{item.label}</span>}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  );
}
