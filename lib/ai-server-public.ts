import type { AiServerConfig } from "@/generated/prisma/client";

export type AiServerPublic = Omit<AiServerConfig, "apiKey"> & {
  hasApiKey: boolean;
};

export function sanitizeAiServer(server: AiServerConfig): AiServerPublic {
  const { apiKey, ...rest } = server;
  return {
    ...rest,
    hasApiKey: Boolean(apiKey?.trim()),
  };
}

export function sanitizeAiServers(servers: AiServerConfig[]): AiServerPublic[] {
  return servers.map(sanitizeAiServer);
}

export function resolveApiKeyFromBody(
  body: { apiKey?: unknown },
  existing?: string | null,
): string | null | undefined {
  if (!("apiKey" in body)) return undefined;
  const raw = body.apiKey;
  if (raw === null || raw === "") return null;
  if (typeof raw === "string") return raw.trim() || null;
  return undefined;
}
