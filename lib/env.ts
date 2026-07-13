/** Bearer de vLLM (--api-key). VLLM_API_KEY tiene prioridad sobre HF_TOKEN (legacy). */
export function getVllmApiKey(): string | undefined {
  const vllm = process.env.VLLM_API_KEY?.trim();
  if (vllm) return vllm;
  const legacy = process.env.HF_TOKEN?.trim();
  return legacy || undefined;
}

/** @deprecated Usar getVllmApiKey — HF_TOKEN se confundía con el token de Hub. */
export function getHfToken(): string | undefined {
  return getVllmApiKey();
}

/** Primero BD (Ajustes), luego VLLM_API_KEY / HF_TOKEN del entorno. */
export function resolveEffectiveApiKey(storedKey?: string | null): string | undefined {
  const fromDb = storedKey?.trim();
  if (fromDb) return fromDb;
  return getVllmApiKey();
}

/** Usar 127.0.0.1 evita fallos con localhost/IPv6/0.0.0.0 en Windows. */
export function getAgentApiUrl(): string {
  const raw = process.env.AGENT_API_URL?.trim() || "http://127.0.0.1:8101";
  return raw
    .replace("://localhost", "://127.0.0.1")
    .replace("://0.0.0.0", "://127.0.0.1")
    .replace(/\/+$/, "");
}

export function buildDatabaseUrl(): string {
  if (process.env.DATABASE_URL) {
    return process.env.DATABASE_URL;
  }

  const user = process.env.DB_USER;
  const password = process.env.DB_PASSWORD ?? "";
  const host = process.env.DB_HOST ?? "localhost";
  const port = process.env.DB_PORT ?? "5432";
  const name = process.env.DB_NAME;
  const schema = process.env.DB_SCHEMA ?? "gptenterprice";

  if (!user || !name) {
    throw new Error(
      "Configura DATABASE_URL o las variables DB_USER, DB_PASSWORD, DB_HOST, DB_PORT y DB_NAME",
    );
  }

  const base = `postgresql://${encodeURIComponent(user)}:${encodeURIComponent(password)}@${host}:${port}/${name}`;
  return `${base}?schema=${encodeURIComponent(schema)}`;
}
