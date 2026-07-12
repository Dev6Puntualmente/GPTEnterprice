import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { requireAuth } from "@/lib/require-auth";

export async function GET() {
  const { session, error } = await requireAuth();
  if (error) return error;

  const projects = await prisma.project.findMany({
    where: { ownerId: session.user.id },
    include: {
      tools: { where: { isActive: true } },
      _count: { select: { conversations: true } },
    },
    orderBy: { createdAt: "desc" },
  });

  return NextResponse.json(projects);
}

export async function POST(request: Request) {
  const { session, error } = await requireAuth();
  if (error) return error;

  const body = await request.json();
  const { name, description, systemPrompt, contextJson } = body;

  if (!name || !systemPrompt) {
    return NextResponse.json(
      { error: "name y systemPrompt son requeridos" },
      { status: 400 },
    );
  }

  const project = await prisma.project.create({
    data: {
      ownerId: session.user.id,
      name,
      description: description ?? null,
      systemPrompt,
      contextJson: contextJson ?? null,
    },
  });

  return NextResponse.json(project, { status: 201 });
}
