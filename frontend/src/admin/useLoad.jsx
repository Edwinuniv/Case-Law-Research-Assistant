// Loads one /api/admin page's data. Returns [data, error, reload].
// Used by every admin page so that each page only describes what it shows.
import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

export function useLoad(path) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const reload = useCallback(() => {
    setError("");
    api(path).then(setData).catch((e) => setError(e.message));
  }, [path]);
  useEffect(reload, [reload]);
  return [data, error, reload];
}

// Shows the error, or "Loading…", or nothing when the data is there.
export function Waiting({ data, error }) {
  if (error) return <p className="error" role="alert">{error}</p>;
  if (!data) return <p className="muted">Loading…</p>;
  return null;
}

// 0.8123 -> "0.81"; null -> "–"
export const num = (v) => (v === null || v === undefined ? "–" : typeof v === "number" ? +v.toFixed(4) : v);
export const day = (iso) => (iso ? iso.slice(0, 16).replace("T", " ") : "");
