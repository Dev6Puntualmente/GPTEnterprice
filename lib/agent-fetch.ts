const TRANSIENT_AGENT_ERROR =
  /fetch failed|ECONNREFUSED|ECONNRESET|ETIMEDOUT|socket hang up|aborted|timeout|network/i;

export function isTransientAgentError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return TRANSIENT_AGENT_ERROR.test(message);
}

export function agentFetchErrorHint(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  if (message.includes("fetch failed") || message.includes("ECONNREFUSED")) {
    return " El agente puede estar arrancando; se reintentó automáticamente.";
  }
  if (message.includes("timeout") || message.includes("aborted")) {
    return " La operación tardó demasiado (presentaciones pueden tardar varios minutos).";
  }
  return "";
}

export type AgentFetchOptions = {
  timeoutMs?: number;
  retries?: number;
  retryDelayMs?: number;
};

/** Fetch a FastAPI con reintentos ante fallos transitorios (arranque, red, puerto ocupado). */
export async function fetchAgent(
  url: string,
  init: RequestInit,
  options: AgentFetchOptions = {},
): Promise<Response> {
  const timeoutMs = options.timeoutMs ?? 120_000;
  const retries = options.retries ?? 2;
  const retryDelayMs = options.retryDelayMs ?? 700;

  let lastError: unknown;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      return await fetch(url, {
        ...init,
        signal: AbortSignal.timeout(timeoutMs),
      });
    } catch (error) {
      lastError = error;
      const transient = isTransientAgentError(error);
      if (!transient || attempt >= retries) {
        throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, retryDelayMs * (attempt + 1)));
    }
  }

  throw lastError;
}
