import { useEffect, useState } from "react";
import { ApiError } from "./client";

export type ApiState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError | Error }
  | { status: "ready"; data: T };

const DEFAULT_TIMEOUT_MS = 15_000;

/** Fetch-on-mount + refetch-on-deps-change, exposing a discriminated state
 * so every page renders exactly one of loading/error/ready — never a silent
 * stale "green" state while a request is failing in the background.
 *
 * A request that never settles (network stall, backend hang) would
 * otherwise leave a page showing "Loading…" forever with no way out except
 * a manual page reload; `timeoutMs` bounds that -- past it, the state moves
 * to a normal, retryable error rather than hanging indefinitely. */
export function useApi<T>(
  fn: () => Promise<T>,
  deps: unknown[] = [],
  timeoutMs: number = DEFAULT_TIMEOUT_MS,
): ApiState<T> & { reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let settled = false;
    setState({ status: "loading" });

    const timer = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      setState({
        status: "error",
        error: new ApiError(0, `Request timed out after ${Math.round(timeoutMs / 1000)}s`, "TIMEOUT"),
      });
    }, timeoutMs);

    fn()
      .then((data) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        setState({ status: "ready", data });
      })
      .catch((error) => {
        if (settled) return;
        settled = true;
        window.clearTimeout(timer);
        setState({ status: "error", error });
      });

    return () => {
      settled = true;
      window.clearTimeout(timer);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, reload: () => setTick((t) => t + 1) } as ApiState<T> & { reload: () => void };
}
