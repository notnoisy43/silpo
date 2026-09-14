const API_BASE = "/api";

export async function getHealth(): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/health`, { credentials: "include" });
  if (!res.ok) throw new Error(`health ${res.status}`);
  return res.json();
}
