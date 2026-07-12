import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@/generated/prisma/client";
import { buildDatabaseUrl } from "@/lib/env";

const globalForPrisma = globalThis as unknown as { prisma?: PrismaClient };

function createPrismaClient() {
  const adapter = new PrismaPg({ connectionString: buildDatabaseUrl() });
  return new PrismaClient({
    adapter,
    log: process.env.NODE_ENV === "development" ? ["error", "warn"] : ["error"],
  });
}

export const prisma = globalForPrisma.prisma ?? createPrismaClient();

if (process.env.NODE_ENV !== "production") globalForPrisma.prisma = prisma;
