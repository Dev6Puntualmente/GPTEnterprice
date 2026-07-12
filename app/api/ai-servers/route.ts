import { AiProviderRole, AiServerType } from "@/generated/prisma/client";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { requireAuth } from "@/lib/require-auth";
import { listUserAiServers, unsetDefaultServers } from "@/lib/server-config-access";

export async function GET() {
  const { session, error } = await requireAuth();
  if (error) return error;

  const servers = await listUserAiServers(session.user.id);
  return NextResponse.json(servers);
}

export async function POST(request: Request) {
  const { session, error } = await requireAuth();
  if (error) return error;

  const existingCount = await prisma.aiServerConfig.count({
    where: { userId: session.user.id },
  });

  if (existingCount > 0) {
    return NextResponse.json(
      { error: "Solo puedes tener un proveedor. Edita el existente." },
      { status: 409 },
    );
  }

  const body = await request.json();
  const {
    name,
    baseUrl,
    modelName,
    type = "VLLM",
    color = "#8b5cf6",
    enabled = true,
    isDefault = true,
  } = body;

  if (!name || !baseUrl || !modelName) {
    return NextResponse.json(
      { error: "name, baseUrl y modelName son requeridos" },
      { status: 400 },
    );
  }

  if (isDefault) {
    await unsetDefaultServers(session.user.id);
  }

  const server = await prisma.aiServerConfig.create({
    data: {
      userId: session.user.id,
      name,
      baseUrl: baseUrl.replace(/\/$/, ""),
      modelName,
      type: type as AiServerType,
      role: AiProviderRole.GENERAL,
      color,
      enabled,
      isDefault: true,
    },
  });

  return NextResponse.json(server, { status: 201 });
}
