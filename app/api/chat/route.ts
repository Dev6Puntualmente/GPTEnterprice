import { MessageRole, Prisma } from "@/generated/prisma/client";
import { NextResponse } from "next/server";
import { prisma } from "@/lib/prisma";
import { requireAuth } from "@/lib/require-auth";
import {
  buildDateContext,
  DEFAULT_CHAT_TIMEOUT_MS,
  looksLikePresentationRequest,
  PRESENTATION_CHAT_TIMEOUT_MS,
} from "@/lib/chat-intent";
import { agentFetchErrorHint, fetchAgent } from "@/lib/agent-fetch";
import { trimChatHistory } from "@/lib/trim-chat-history";
import { getAgentApiUrl } from "@/lib/env";
import { resolveUserLlmEndpoint } from "@/lib/server-config-access";
import type { ChatResponse, ToolDefinition } from "@/lib/types";

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
  messages: Array<{
    role: MessageRole;
    content: string;
    toolName?: string | null;
    toolCallId?: string | null;
  }>,
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
  const { session, error } = await requireAuth();
  if (error) return error;

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
    (await prisma.conversation.findFirst({
      where: { id: conversationId, userId: session.user.id },
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

    const project = await prisma.project.findFirst({
      where: { id: body.projectId, ownerId: session.user.id },
      include: { tools: { where: { isActive: true } } },
    });

    if (!project) {
      return NextResponse.json({ error: "Proyecto no encontrado" }, { status: 404 });
    }

    conversation = await prisma.conversation.create({
      data: {
        projectId: project.id,
        userId: session.user.id,
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

  const history = trimChatHistory([
    ...conversation.messages,
    { role: MessageRole.USER, content: message.trim(), toolName: null, toolCallId: null },
  ]);
  const contextBlock = conversation.project.contextJson
    ? `\n\nContexto del proyecto:\n${JSON.stringify(conversation.project.contextJson)}`
    : "";
  const dateContext = buildDateContext();
  const agentApiUrl = getAgentApiUrl();
  const chatUrl = `${agentApiUrl}/chat`;
  const llmEndpoint = await resolveUserLlmEndpoint(session.user.id);

  let agentResponse: Response;
  try {
    console.info("[chat] contacting FastAPI:", chatUrl);
    agentResponse = await fetchAgent(
      chatUrl,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          system_prompt: `${conversation.project.systemPrompt}\n\n${dateContext}${contextBlock}`,
          messages: toAgentMessages(history),
          tools: toOpenAiTools(conversation.project.tools),
          vllm: llmEndpoint
            ? {
                base_url: llmEndpoint.baseUrl,
                model: llmEndpoint.modelName,
                ...(llmEndpoint.apiKey ? { api_key: llmEndpoint.apiKey } : {}),
              }
            : null,
        }),
      },
      {
        timeoutMs: looksLikePresentationRequest(message)
          ? PRESENTATION_CHAT_TIMEOUT_MS
          : DEFAULT_CHAT_TIMEOUT_MS,
        retries: 2,
      },
    );
  } catch (agentError) {
    const detail =
      agentError instanceof Error ? agentError.message : "FastAPI no está disponible";
    const hint = agentFetchErrorHint(agentError);
    return NextResponse.json(
      { error: "No se pudo contactar FastAPI", detail: `${detail}${hint}`, agentApiUrl, chatUrl },
      { status: 502 },
    );
  }

  if (!agentResponse.ok) {
    const errorText = await agentResponse.text();
    let detail = errorText;
    try {
      const parsed = JSON.parse(errorText) as { detail?: string };
      detail = parsed.detail ?? errorText;
    } catch {
      // keep raw text
    }
    return NextResponse.json(
      { error: "Error al contactar el agente", detail, agentApiUrl, chatUrl },
      { status: 502 },
    );
  }

  const agentData = (await agentResponse.json()) as ChatResponse & {
    pending_job?: ChatResponse["pending_job"];
  };

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
        model_used: agentData.pending_job ? "worker" : agentData.model_used,
        files: agentData.files ?? [],
        pending_job: agentData.pending_job ?? undefined,
        job_status: agentData.pending_job?.status,
        job_progress: agentData.pending_job?.progress,
        job_stage: agentData.pending_job?.stage,
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
    modelUsed: agentData.pending_job ? "worker" : agentData.model_used,
    toolCalls: agentData.tool_calls,
    files: agentData.files,
    pendingJob: agentData.pending_job ?? null,
    agentApiUrl,
  });
}
