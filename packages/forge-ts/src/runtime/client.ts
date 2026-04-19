/**
 * Forge runtime client — handles all API communication.
 * UI developers never use this directly.
 */

const DEFAULT_BASE_URL =
  typeof window !== "undefined"
    ? window.location.origin
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

export interface StreamHandlers {
  onEvent?: (event: string, data: string) => void;
  onDone?: () => void;
  onError?: (err: Error) => void;
}

export async function callStreamingEndpoint(
  endpointId: string,
  body: Record<string, unknown>,
  handlers: StreamHandlers
): Promise<void> {
  const res = await fetch(`${_baseUrl}/endpoints/${endpointId}/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    handlers.onError?.(new Error(`Streaming endpoint ${endpointId} failed (${res.status})`));
    return;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const blocks = buf.split("\n\n");
    buf = blocks.pop() ?? "";
    for (const block of blocks) {
      if (!block.trim()) continue;
      let eventType = "message";
      let data = "";
      for (const line of block.split("\n")) {
        if (line.startsWith("event: ")) eventType = line.slice(7).trim();
        else if (line.startsWith("data: ")) data = line.slice(6);
      }
      if (eventType === "done") { handlers.onDone?.(); return; }
      if (eventType === "error") { handlers.onError?.(new Error(data)); return; }
      handlers.onEvent?.(eventType, data);
    }
  }
  handlers.onDone?.();
}
