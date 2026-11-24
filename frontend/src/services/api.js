import axios from "axios";

/**
 * Single axios instance for the whole app.
 * - Auth uses an HttpOnly session cookie set by the backend (no tokens in JS / localStorage).
 * - Every request carries the custom X-Requested-With header the backend requires for CSRF protection.
 */
export const api = axios.create({
  baseURL: "/api",
  withCredentials: true,
  headers: { "X-Requested-With": "SAMS" },
  timeout: 30000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url || "";
    if (status === 401 && !url.startsWith("/auth/")) {
      window.dispatchEvent(new CustomEvent("sams:unauthorized", { detail: error.response?.data }));
    }
    return Promise.reject(error);
  },
);

export function errorMessage(error, fallback = "Something went wrong. Please try again.") {
  if (!error) return fallback;
  if (error.response?.data instanceof Blob) return fallback;
  const detail = error.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  if (error.code === "ECONNABORTED") return "The server took too long to respond.";
  if (!error.response) return "Cannot reach the server. Is the backend running on port 8000?";
  return fallback;
}

/** Download a binary file (PDF / Excel) through the authenticated API and save it. */
export async function downloadFile(url, fallbackName) {
  const res = await api.get(url, { responseType: "blob" });
  const disposition = res.headers["content-disposition"] || "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const name = match ? match[1] : fallbackName;
  const href = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = href;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(href), 2000);
  return name;
}

/** Same as downloadFile, but surfaces JSON error bodies returned as blobs. */
export async function safeDownload(url, fallbackName) {
  try {
    return await downloadFile(url, fallbackName);
  } catch (error) {
    if (error.response?.data instanceof Blob) {
      try {
        const text = await error.response.data.text();
        error.response.data = JSON.parse(text);
      } catch {
        /* keep original */
      }
    }
    throw error;
  }
}
