import { AiServerType } from "@/generated/prisma/client";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { requireAuth } from "@/lib/require-auth";
import {
  findAccessibleAiServer,
  unsetDefaultServers,
} from "@/lib/server-config-access";

type RouteContext = { params: Promise<{ id: string }> };

export async function GET(_request: Request, context: RouteContext) {
  const { session, error } = await requireAuth();
  if (error) return error;

  const { id } = await context.params;
  const server = await findAccessibleAiServer(id, session.user.id, session.user.role as "ADMIN");

  if (!server) {
    return NextResponse.json({ error: "Servidor no encontrado" }, { status: 404 });
  }

  return NextResponse.json(server);
}

export async function PATCH(request: Request, context: RouteContext) {
  const { session, error } = await requireAuth();
  if (error) return error;

  const { id } = await context.params;
  const existing = await findAccessibleAiServer(id, session.user.id, session.user.role as "ADMIN");

  if (!existing) {
    return NextResponse.json({ error: "Servidor no encontrado" }, { status: 404 });
  }

  const body = await request.json();

  if (body.isDefault) {
    await unsetDefaultServers(session.user.id, id);
  }

  const server = await prisma.aiServerConfig.update({
    where: { id },
    data: {
      name: body.name,
      baseUrl: body.baseUrl?.replace(/\/$/, ""),
      modelName: body.modelName,
      type: body.type as AiServerType | undefined,
      color: body.color,
      enabled: body.enabled,
      isDefault: body.isDefault ?? true,
    },
  });

  return NextResponse.json(server);
}

export async function DELETE(_request: Request, context: RouteContext) {
  const { session, error } = await requireAuth();
  if (error) return error;

  const { id } = await context.params;
  const existing = await findAccessibleAiServer(id, session.user.id, session.user.role as "ADMIN");

  if (!existing) {
    return NextResponse.json({ error: "Servidor no encontrado" }, { status: 404 });
  }

  await prisma.aiServerConfig.delete({ where: { id } });
  return NextResponse.json({ ok: true });
}
