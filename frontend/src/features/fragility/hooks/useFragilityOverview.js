import { useCallback } from "react";
import { useAsyncData } from "../../../hooks/useAsyncData";
import { getFragilityAnalysis } from "../../../services/fragilityService";

export function useFragilityAnalysis() {
  return useAsyncData(useCallback(() => getFragilityAnalysis(), []), {
    errorMessage: "Failed to load portfolio fragility",
  });
}
