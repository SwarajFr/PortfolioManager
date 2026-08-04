/**
 * The shared axios instance. Every service imports this — note it is a **named**
 * export, `{ apiClient }`, not a default.
 *
 * The response interceptor exists so callers never have to dig through axios's
 * error shape. FastAPI puts its message in `response.data.detail`, which is
 * where a `raise HTTPException(...)` string lands; that is unwrapped here into
 * a plain `Error`, so a `catch` block can show `error.message` and get the
 * backend's own wording rather than "Request failed with status code 400".
 *
 * The 120s timeout is sized for the slowest legitimate call, not a typical one:
 * a screener refresh walks ~500 symbols against a rate-limited broker API, and
 * an Agent turn waits on a local LLM. Both routinely outlast a default timeout.
 */
import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api";

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120000,
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const message =
      error.response?.data?.detail ||
      error.response?.data?.message ||
      error.message ||
      "Request failed";

    return Promise.reject(new Error(message));
  },
);

export { API_BASE_URL };
