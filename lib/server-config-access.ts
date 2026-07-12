import type { AiServerConfig, UserRole } from "@/generated/prisma/client";
import { getHfToken } from "@/lib/env";
import { prisma } from "@/lib/prisma";

export type SessionUser = {
  id: string;
  role: UserRole;
};

export function canManageAllAiServers(user: SessionUser): boolean {
  return user.role === "ADMIN";
}

export async function findAccessibleAiServer(
  serverId: string,
  userId: string,
  role?: UserRole,
): Promise<AiServerConfig | null> {
  const server = await prisma.aiServerConfig.findUnique({ where: { id: serverId } });
  if (!server) return null;
  if (canManageAllAiServers({ id: userId, role: role ?? "OPERATOR" })) return server;
  if (server.userId === userId) return server;
  return null;
}

export async function listUserAiServers(userId: string) {
  return prisma.aiServerConfig.findMany({
    where: { userId },
    orderBy: [{ isDefault: "desc" }, { createdAt: "asc" }],
  });
}

export type LlmEndpoint = {
  baseUrl: string;
  modelName: string;
  apiKey?: string | null;
};

function withHfToken(endpoint: LlmEndpoint): LlmEndpoint {
  return {
    ...endpoint,
    apiKey: endpoint.apiKey ?? getHfToken() ?? null,
  };
}

/** Proveedor único (Phi) — chat y tools usan el mismo endpoint. */
export async function resolveUserLlmEndpoint(userId: string): Promise<LlmEndpoint | null> {
  const servers = await prisma.aiServerConfig.findMany({
    where: { userId, enabled: true },
    orderBy: [{ isDefault: "desc" }, { createdAt: "asc" }],
    take: 1,
  });

  const server = servers[0];
  if (!server) return null;

  return withHfToken({
    baseUrl: server.baseUrl,
    modelName: server.modelName,
    apiKey: server.apiKey,
  });
}

export async function unsetDefaultServers(userId: string, exceptId?: string) {
  await prisma.aiServerConfig.updateMany({
    where: {
      userId,
      ...(exceptId ? { id: { not: exceptId } } : {}),
    },
    data: { isDefault: false },
  });
}
