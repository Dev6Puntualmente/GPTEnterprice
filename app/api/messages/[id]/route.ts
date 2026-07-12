import { Prisma } from "@/generated/prisma/client";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { requireAuth } from "@/lib/require-auth";

export async function PATCH(
  request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { session, error } = await requireAuth();
  if (error) return error;

  const { id } = await context.params;
  const body = (await request.json()) as { metadata?: Record<string, unknown> };

  const message = await prisma.message.findFirst({
    where: { id },
    include: { conversation: true },
  });

  if (!message || message.conversation.userId !== session.user.id) {
    return NextResponse.json({ error: "Mensaje no encontrado" }, { status: 404 });
  }

  const currentMetadata =
    message.metadata && typeof message.metadata === "object"
      ? (message.metadata as Record<string, unknown>)
      : {};

  const updated = await prisma.message.update({
    where: { id },
    data: {
      metadata: {
        ...currentMetadata,
        ...body.metadata,
      } as Prisma.InputJsonValue,
    },
  });

  return NextResponse.json(updated);
}
