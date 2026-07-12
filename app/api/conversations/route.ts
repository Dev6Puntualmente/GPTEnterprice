import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);
  const projectId = searchParams.get("projectId");

  if (!projectId) {
    return NextResponse.json({ error: "projectId es requerido" }, { status: 400 });
  }

  const conversations = await prisma.conversation.findMany({
    where: { projectId },
    orderBy: { updatedAt: "desc" },
    include: {
      messages: {
        orderBy: { createdAt: "asc" },
        take: 1,
      },
    },
  });

  return NextResponse.json(conversations);
}

export async function POST(request: Request) {
  const body = await request.json();
  const { projectId, title } = body;

  if (!projectId) {
    return NextResponse.json({ error: "projectId es requerido" }, { status: 400 });
  }

  const conversation = await prisma.conversation.create({
    data: {
      projectId,
      title: title ?? "Nueva conversación",
    },
  });

  return NextResponse.json(conversation, { status: 201 });
}
