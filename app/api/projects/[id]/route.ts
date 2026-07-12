import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { requireAuth } from "@/lib/require-auth";

type RouteContext = { params: Promise<{ id: string }> };

export async function GET(_request: Request, context: RouteContext) {
  const { session, error } = await requireAuth();
  if (error) return error;

  const { id } = await context.params;
  const project = await prisma.project.findFirst({
    where: { id, ownerId: session.user.id },
    include: { tools: { where: { isActive: true } } },
  });

  if (!project) {
    return NextResponse.json({ error: "Proyecto no encontrado" }, { status: 404 });
  }

  return NextResponse.json(project);
}

export async function PATCH(request: Request, context: RouteContext) {
  const { session, error } = await requireAuth();
  if (error) return error;

  const { id } = await context.params;
  const existing = await prisma.project.findFirst({
    where: { id, ownerId: session.user.id },
  });

  if (!existing) {
    return NextResponse.json({ error: "Proyecto no encontrado" }, { status: 404 });
  }

  const body = await request.json();
  const project = await prisma.project.update({
    where: { id },
    data: {
      name: body.name,
      description: body.description,
      systemPrompt: body.systemPrompt,
      contextJson: body.contextJson,
    },
  });

  return NextResponse.json(project);
}
