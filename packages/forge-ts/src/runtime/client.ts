/**
 * Forge runtime client — handles all API communication.
 * UI developers never use this directly.
 */

const DEFAULT_BASE_URL =
  typeof window !== "undefined"
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : "http://localhost:8000";

let _baseUrl = DEFAULT_BASE_URL;

export function configureForge(options: { baseUrl?: string }) {
  if (options.baseUrl) _baseUrl = options.baseUrl;
}

export async function callEndpoint<T = unknown>(
  endpointId: string,
  body: Record<string, unknown>
): Promise<T> {
  const res = await fetch(`${_baseUrl}/endpoints/${endpointId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`Endpoint ${endpointId} failed (${res.status}): ${text}`);
  }
  return res.json() as Promise<T>;
}

export async function fetchObjectSet<T>(
  objectType: string,
  options?: { limit?: number; offset?: number }
): Promise<{ rows: T[]; total: number; schema: unknown }> {
  const params = new URLSearchParams();
  if (options?.limit) params.set("limit", String(options.limit));
  if (options?.offset) params.set("offset", String(options.offset));
  const res = await fetch(`${_baseUrl}/api/objects/${objectType}?${params}`);
  if (!res.ok) throw new Error(`fetchObjectSet failed for ${objectType}`);
  return res.json();
}

export async function fetchEndpointDescriptor(
  endpointId: string
): Promise<unknown> {
  const res = await fetch(`${_baseUrl}/api/endpoints`);
  if (!res.ok) throw new Error("Failed to fetch endpoint registry");
  const registry = await res.json();
  return registry[endpointId] ?? null;
}

export async function fetchAllEndpoints(): Promise<
  Record<string, unknown>
> {
  const res = await fetch(`${_baseUrl}/api/endpoints`);
  if (!res.ok) throw new Error("Failed to fetch endpoint registry");
  return res.json();
}

export async function triggerPipeline(name: string): Promise<unknown> {
  const res = await fetch(`${_baseUrl}/api/pipelines/${name}/run`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Failed to trigger pipeline ${name}`);
  return res.json();
}
