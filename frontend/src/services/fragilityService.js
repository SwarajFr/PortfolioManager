import { apiClient } from "./apiClient";

export async function getFragilityAnalysis() {
  const { data } = await apiClient.get("/fragility/analysis");
  return data;
}
