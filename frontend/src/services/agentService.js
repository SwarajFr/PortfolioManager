import { apiClient } from "./apiClient";

export async function postChat(messages) {
  const { data } = await apiClient.post("/agent/chat", { messages });
  return data;
}
