import { useApi } from "../api/useApi";
import { api } from "../api/client";
import { ErrorState } from "../components/ErrorState";

export function Migrations() {
  const migrations = useApi(api.migrations, []);

  return (
    <div className="page">
      <div className="page-header">
        <h1>Migrations</h1>
      </div>
      <p style={{ color: "var(--ink-dim)", maxWidth: 640, marginBottom: "var(--space-5)" }}>
        Read-only schema migration state. There is no migration-execution control in ARENA — migrations are applied
        by the Foundation CLI, never from this UI.
      </p>

      {migrations.status === "error" && (
        <ErrorState error={migrations.error} dependency="migration state" onRetry={migrations.reload} />
      )}

      {migrations.status === "ready" && (
        <section className="panel">
          <h2 className="panel-heading">
            {migrations.data.up_to_date ? "Up to date" : `${migrations.data.pending.length} pending`} ·{" "}
            {migrations.data.total_migrations} total
          </h2>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Migration</th>
                <th scope="col">State</th>
              </tr>
            </thead>
            <tbody>
              {migrations.data.applied.map((v) => (
                <tr key={v}>
                  <td className="mono">{v}</td>
                  <td>
                    <span className="status-badge status-badge--ok">
                      <span className="status-badge__dot" aria-hidden="true" />
                      Applied
                    </span>
                  </td>
                </tr>
              ))}
              {migrations.data.pending.map((v) => (
                <tr key={v}>
                  <td className="mono">{v}</td>
                  <td>
                    <span className="status-badge status-badge--degraded">
                      <span className="status-badge__dot" aria-hidden="true" />
                      Pending
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      )}
    </div>
  );
}
