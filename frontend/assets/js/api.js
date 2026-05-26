const BASE = "/api/dashboard";
const PROFILE_BASE = "/api/profile";

async function apiFetch(path, options = {}) {
  const res = await fetch(BASE + path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API Error");
  }
  return res.json();
}

async function profileFetch(path, options = {}) {
  const res = await fetch(PROFILE_BASE + path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API Error");
  }
  if (res.status === 204) return null;
  return res.json();
}

export const api = {
  stats: () => apiFetch("/stats"),
  riskScore: () => apiFetch("/risk-score"),
  trend: () => apiFetch("/trend"),
  platformStats: () => apiFetch("/platform-stats"),
  threats: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v != null && v !== ""))
    ).toString();
    return apiFetch(`/threats${qs ? "?" + qs : ""}`);
  },
  alerts: (limit = 10) => apiFetch(`/alerts?limit=${limit}`),
  updateStatus: (id, status) =>
    apiFetch(`/threats/${id}/status`, {
      method: "PATCH",
      body: JSON.stringify({ status }),
    }),
  scan: (keywords = [], platforms = "all") =>
    apiFetch("/scan", {
      method: "POST",
      body: JSON.stringify({ keywords, platforms }),
    }),
  sentimentTrend: () => apiFetch("/sentiment-trend"),
  shareOfVoice: () => apiFetch("/share-of-voice"),
  topInfluencers: (limit = 10) => apiFetch(`/top-influencers?limit=${limit}`),
};

async function assistantFetch(path, options = {}) {
  const res = await fetch("/api/assistant" + path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API Error");
  }
  return res.json();
}

export const assistantApi = {
  chat: (message, context = "") => assistantFetch("/chat", {
    method: "POST",
    body: JSON.stringify({ message, context }),
  }),
};

async function keywordFetch(path, options = {}) {
  const res = await fetch("/api/keywords" + path, {
    headers: { "Content-Type": "application/json", ...options.headers },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "API Error");
  }
  if (res.status === 204) return null;
  return res.json();
}

export const keywordApi = {
  list: () => keywordFetch(""),
  create: (keyword, platforms) => keywordFetch("", { method: "POST", body: JSON.stringify({ keyword, platforms }) }),
  delete: (id) => keywordFetch(`/${id}`, { method: "DELETE" }),
};

export const profileApi = {
  list:            ()         => profileFetch(""),
  create:          (body)     => profileFetch("",                          { method: "POST",   body: JSON.stringify(body) }),
  update:          (id, body) => profileFetch(`/${id}`,                    { method: "PATCH",  body: JSON.stringify(body) }),
  addAlias:        (id, body) => profileFetch(`/${id}/aliases`,            { method: "POST",   body: JSON.stringify(body) }),
  deleteAlias:     (id, aId)  => profileFetch(`/${id}/aliases/${aId}`,     { method: "DELETE" }),
  addSocial:       (id, body) => profileFetch(`/${id}/social-accounts`,    { method: "POST",   body: JSON.stringify(body) }),
  deleteSocial:    (id, aId)  => profileFetch(`/${id}/social-accounts/${aId}`, { method: "DELETE" }),
  addExecutive:    (id, body) => profileFetch(`/${id}/executives`,         { method: "POST",   body: JSON.stringify(body) }),
  deleteExecutive: (id, eId)  => profileFetch(`/${id}/executives/${eId}`,  { method: "DELETE" }),
};
