import { API_BASE_URL, apiClient } from "./apiClient";

export async function getAuthStatus() {
  const { data } = await apiClient.get("/auth/status");
  // userId names the Zerodha account the backend is scoped to — shown in the
  // rail so it is always visible whose data is on screen.
  return { authenticated: Boolean(data.authenticated), userId: data.user_id ?? null };
}

export function redirectToKiteLogin() {
  window.location.href = `${API_BASE_URL}/auth/login`;
}
