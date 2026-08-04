/**
 * Load-on-mount async data with loading/error state and a manual refresh.
 *
 * `useReducer` rather than three `useState` calls, for a lint reason that is
 * also a correctness reason: the config enforces
 * `react-hooks/set-state-in-effect` as an error, and a single dispatch moves
 * data, error and loading in one transition — so there is no render where
 * `loading` is already false but `data` has not landed yet.
 *
 * `cancelled` guards the late-resolve case: a component unmounted (or the
 * loader changed) while a request was in flight would otherwise dispatch into
 * a dead reducer and, worse, fire a toast for a screen nobody is looking at.
 *
 * Note `options` is an object, not a deps array — `useAsyncData(fn, { errorMessage })`.
 * The effect re-runs when `loader` changes identity, so callers must memoise
 * anything they build inline, or it will refetch on every render.
 */
import { useEffect, useReducer } from "react";
import toast from "react-hot-toast";

function reducer(state, action) {
  switch (action.type) {
    case "loading":
      return { ...state, error: null, loading: true };
    case "success":
      return { ...state, data: action.payload, error: null, loading: false };
    case "error":
      return { ...state, error: action.payload, loading: false };
    default:
      return state;
  }
}

export function useAsyncData(loader, options = {}) {
  const { errorMessage = "Failed to load data", enabled = true } = options;
  const [refreshKey, forceRefresh] = useReducer((value) => value + 1, 0);
  const [state, dispatch] = useReducer(reducer, {
    data: null,
    error: null,
    loading: Boolean(enabled),
  });

  useEffect(() => {
    if (!enabled) return undefined;

    let cancelled = false;
    dispatch({ type: "loading" });

    loader()
      .then((payload) => {
        if (!cancelled) {
          dispatch({ type: "success", payload });
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          dispatch({ type: "error", payload: loadError });
          toast.error(errorMessage);
        }
      })

    return () => {
      cancelled = true;
    };
  }, [enabled, errorMessage, loader, refreshKey]);

  return {
    ...state,
    refresh: forceRefresh,
  };
}
