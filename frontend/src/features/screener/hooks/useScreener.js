import { useCallback } from "react";
import { useAsyncData } from "../../../hooks/useAsyncData";
import { getStrategies, getStatus } from "../../../services/screenerService";

export function useStrategies() {
  return useAsyncData(useCallback(() => getStrategies(), []), {
    errorMessage: "Failed to load strategies",
  });
}

export function useScreenerStatus() {
  return useAsyncData(useCallback(() => getStatus(), []), {
    errorMessage: "Failed to load screener status",
  });
}
