import { apiClient } from "./apiClient";

export async function getAdvisorProfile() {
  const { data } = await apiClient.get("/advisor/profile");
  return data;
}

export async function saveAdvisorProfile(profile) {
  const { data } = await apiClient.put("/advisor/profile", { profile });
  return data;
}

export async function resetAdvisorProfile() {
  const { data } = await apiClient.post("/advisor/profile/reset");
  return data;
}

export async function getPortfolioActions(params = {}) {
  const { data } = await apiClient.get("/advisor/actions", { params });
  return data;
}

export async function getBuyIdeas(params = {}) {
  const { data } = await apiClient.get("/advisor/ideas", { params });
  return data;
}

export async function getAdviceJournal(params = {}) {
  const { data } = await apiClient.get("/advisor/journal", { params });
  return data;
}
