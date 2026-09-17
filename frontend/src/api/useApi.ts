import { useEffect, useState } from "react";
import { ApiError } from "./client";

export type ApiState<T> =
  | { status: "loading" }
  | { status: "error"; error: ApiError | Error }
  | { status: "ready"; data: T };

/** Fetch-on-mount + refetch-on-deps-change, exposing a discriminated state
 * so every page renders exactly one of loading/error/ready — never a silent
 * stale "green" state while a request is failing in the background. */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []): ApiState<T> & { reload: () => void } {
  const [state, setState] = useState<ApiState<T>>({ status: "loading" });
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setState({ status: "loading" });
    fn()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((error) => {
        if (!cancelled) setState({ status: "error", error });
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);

  return { ...state, reload: () => setTick((t) => t + 1) } as ApiState<T> & { reload: () => void };
}
