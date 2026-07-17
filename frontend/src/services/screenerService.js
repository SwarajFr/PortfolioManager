import { apiClient } from "./apiClient";

export async function getStrategies() {
  const { data } = await apiClient.get("/screener/strategies");
  return data;
}

export async function getIndividual(strategy) {
  const { data } = await apiClient.get("/screener/individual", { params: { strategy } });
  return data;
}

export async function postScan(body) {
  const { data } = await apiClient.post("/screener/scan", body);
  return data;
}

export async function postRefresh() {
  const { data } = await apiClient.post("/screener/refresh");
  return data;
}

export async function getStatus() {
  const { data } = await apiClient.get("/screener/status");
  return data;
}
