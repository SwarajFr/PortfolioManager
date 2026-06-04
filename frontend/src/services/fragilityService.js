import { apiClient } from "./apiClient";

export async function getFragilityAnalysis() {
  const { data } = await apiClient.get("/fragility/analysis");
  return data;
}

export async function getFragilityWhatIf(ticker, newWeight) {
  const { data } = await apiClient.get("/fragility/whatif", {
    params: { ticker, new_weight: newWeight },
  });
  return data;
}
