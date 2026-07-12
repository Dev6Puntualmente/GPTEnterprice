import { MessageRole, Prisma } from "@prisma/client";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import type { ChatResponse, ToolDefinition } from "@/lib/types";

const AGENT_API_URL = process.env.AGENT_API_URL ?? "http://localhost:8100";

function toOpenAiTools(
  tools: Array<{
    name: string;
    description: string;
    parameters: unknown;
  }>,
): ToolDefinition[] {
  return tools.map((tool) => ({
    type: "function",
    function: {
      name: tool.name,
      description: tool.description,
      parameters: (tool.parameters as Record<string, unknown>) ?? {
        type: "object",
        properties: {},
      },
    },
  }));
}

function toAgentMessages(
  messages: Array<{ role: MessageRole; content: string; toolName?: string | null; toolCallId?: string | null }>,
) {
  return messages
    .filter((message) => message.role !== "SYSTEM")
    .map((message) => {
      if (message.role === "TOOL") {
        return {
          role: "tool" as const,
          content: message.content,
          name: message.toolName ?? undefined,
          tool_call_id: message.toolCallId ?? undefined,
        };
      }

      return {
        role: message.role.toLowerCase() as "user" | "assistant",
        content: message.content,
      };
    });
}

export async function POST(request: Request) {
  const body = await request.json();
  const { conversationId, message } = body as {
    conversationId?: string;
    projectId?: string;
    message?: string;
  };

  if (!message?.trim()) {
    return NextResponse.json({ error: "message es requerido" }, { status: 400 });
  }

  let conversation =
    conversationId &&
    (await prisma.conversation.findUnique({
      where: { id: conversationId },
      include: {
        project: { include: { tools: { where: { isActive: true } } } },
        messages: { orderBy: { createdAt: "asc" } },
      },
    }));

  if (!conversation) {
    if (!body.projectId) {
      return NextResponse.json(
        { error: "conversationId o projectId es requerido" },
        { status: 400 },
      );
    }

    const project = await prisma.project.findUnique({
      where: { id: body.projectId },
      include: { tools: { where: { isActive: true } } },
    });

    if (!project) {
      return NextResponse.json({ error: "Proyecto no encontrado" }, { status: 404 });
    }

    conversation = await prisma.conversation.create({
      data: {
        projectId: project.id,
        title: message.slice(0, 60),
      },
      include: {
        project: { include: { tools: { where: { isActive: true } } } },
        messages: true,
      },
    });
  }

  await prisma.message.create({
    data: {
      conversationId: conversation.id,
      role: MessageRole.USER,
      content: message.trim(),
    },
  });

  const history = [...conversation.messages, { role: MessageRole.USER, content: message.trim(), toolName: null, toolCallId: null }];
  const contextBlock = conversation.project.contextJson
    ? `\n\nContexto del proyecto:\n${JSON.stringify(conversation.project.contextJson, null, 2)}`
    : "";

  const agentResponse = await fetch(`${AGENT_API_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      system_prompt: `${conversation.project.systemPrompt}${contextBlock}`,
      messages: toAgentMessages(history),
      tools: toOpenAiTools(conversation.project.tools),
    }),
  });

  if (!agentResponse.ok) {
    const errorText = await agentResponse.text();
    return NextResponse.json(
      { error: "Error al contactar el agente", detail: errorText },
      { status: 502 },
    );
  }

  const agentData = (await agentResponse.json()) as ChatResponse;

  if (agentData.tool_calls?.length) {
    for (const toolCall of agentData.tool_calls) {
      await prisma.message.create({
        data: {
          conversationId: conversation.id,
          role: MessageRole.TOOL,
          content: toolCall.result,
          toolName: toolCall.name,
          metadata: {
            arguments: toolCall.arguments,
          } as Prisma.InputJsonValue,
        },
      });
    }
  }

  const assistantMessage = await prisma.message.create({
    data: {
      conversationId: conversation.id,
      role: MessageRole.ASSISTANT,
      content: agentData.message,
      metadata: {
        model_used: agentData.model_used,
        files: agentData.files ?? [],
      } as Prisma.InputJsonValue,
    },
  });

  await prisma.conversation.update({
    where: { id: conversation.id },
    data: { updatedAt: new Date() },
  });

  return NextResponse.json({
    conversationId: conversation.id,
    message: assistantMessage,
    modelUsed: agentData.model_used,
    toolCalls: agentData.tool_calls,
    files: agentData.files,
  });
}
