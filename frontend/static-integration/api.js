const API_BASE = window.API_BASE_URL || "http://127.0.0.1:5000";

async function requestJson(path, params = {}) {
  const query = new URLSearchParams(params);
  const url = `${API_BASE}${path}${query.toString() ? `?${query.toString()}` : ""}`;
  const response = await fetch(url, { method: "GET" });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Request failed (${response.status}): ${text}`);
  }
  return response.json();
}

export function fetchInternships(params = {}) {
  return requestJson("/internships", params);
}

export function fetchInternshipStats() {
  return requestJson("/internships/stats");
}

export function fetchMentorships(params = {}) {
  return requestJson("/mentorships", params);
}

export function fetchMentorshipStats() {
  return requestJson("/mentorships/stats");
}
