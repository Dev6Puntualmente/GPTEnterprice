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
  tools: Array<{ name: string; description: string; parameters: unknown }>,
): ToolDefinition[] {
  return tools.map((tool) => ({
    type: "function" as const,
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

type StreamEvent =
  | { type: "token"; content: string }
  | { type: "status"; content?: string }
  | { type: "error"; message?: string }
  | {
      type: "done";
      model_used?: string;
      message?: string | { content?: string };
      tool_calls?: ChatResponse["tool_calls"];
      pending_job?: ChatResponse["pending_job"];
      files?: string[];
    };

function extractFinalText(
  doneEvent: Extract<StreamEvent, { type: "done" }> | null,
  fullText: string,
): string {
  const streamed = fullText.trim();
  const raw = doneEvent?.message;
  if (typeof raw === "string" && raw.trim()) {
    return raw.trim();
  }
  if (raw && typeof raw === "object" && typeof raw.content === "string" && raw.content.trim()) {
    return raw.content.trim();
  }
  return streamed;
}

function parseSseChunk(buffer: string): { events: StreamEvent[]; rest: string } {
  const events: StreamEvent[] = [];
  const parts = buffer.split("\n\n");
  const rest = parts.pop() ?? "";
  for (const part of parts) {
    const line = part
      .split("\n")
      .find((entry) => entry.startsWith("data: "));
    if (!line) continue;
    try {
      events.push(JSON.parse(line.slice(6)) as StreamEvent);
    } catch {
      // ignore malformed
    }
  }
  return { events, rest };
}

export async function POST(request: Request) {
  const { session, error } = await requireAuth();
  if (error) return error;

  const body = await request.json();
  const { conversationId, message } = body as {
    conversationId?: string;
    projectId?: string;
    message?: string;
    stream?: boolean;
  };
  const streamRequested = true;

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
  const llmEndpoint = await resolveUserLlmEndpoint(session.user.id);
  const agentApiUrl = getAgentApiUrl();
  const chatUrl = `${agentApiUrl}/chat`;

  let agentResponse: Response;
  try {
    agentResponse = await fetchAgent(
      chatUrl,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          system_prompt: `${conversation.project.systemPrompt}\n\n${dateContext}${contextBlock}`,
          messages: toAgentMessages(history),
          tools: toOpenAiTools(conversation.project.tools),
          stream: streamRequested,
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
          : streamRequested
            ? DEFAULT_CHAT_TIMEOUT_MS
            : 180_000,
        retries: 2,
      },
    );
  } catch (agentError) {
    const detail =
      agentError instanceof Error ? agentError.message : "FastAPI no está disponible";
    const hint =
      detail.includes("fetch failed") || detail.includes("ECONNREFUSED")
        ? " Verifica que FastAPI esté en el puerto 8101 (npm run backend:start)."
        : detail.includes("timeout") || detail.includes("aborted")
          ? " FastAPI no respondió a tiempo — puede estar bloqueado por CRM o vLLM."
          : agentFetchErrorHint(agentError);
    return NextResponse.json(
      {
        error: "No se pudo contactar FastAPI",
        detail: `${detail}${hint}`,
        agentApiUrl: chatUrl,
      },
      { status: 502 },
    );
  }

  async function readAgentError(response: Response): Promise<string> {
    const raw = await response.text();
    try {
      const parsed = JSON.parse(raw) as { detail?: string; error?: string };
      return parsed.detail ?? parsed.error ?? raw;
    } catch {
      return raw || `HTTP ${response.status}`;
    }
  }

  const contentType = agentResponse.headers.get("content-type") ?? "";

  // Excel / jobs: FastAPI responde JSON aunque pidamos stream
  if (contentType.includes("application/json")) {
    if (!agentResponse.ok) {
      const detail = await readAgentError(agentResponse);
      return NextResponse.json(
        { error: "Error del agente", detail, agentApiUrl: chatUrl },
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
            metadata: { arguments: toolCall.arguments } as Prisma.InputJsonValue,
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

    return NextResponse.json({
      conversationId: conversation.id,
      message: assistantMessage,
      pendingJob: agentData.pending_job ?? null,
      stream: false,
    });
  }

  if (!agentResponse.ok || !agentResponse.body) {
    const detail = agentResponse.ok
      ? "El agente no devolvió cuerpo de stream"
      : await readAgentError(agentResponse);
    return NextResponse.json(
      { error: "Error en stream del agente", detail, agentApiUrl: chatUrl },
      { status: 502 },
    );
  }

  const convId = conversation.id;
  const encoder = new TextEncoder();
  const decoder = new TextDecoder();
  const upstream = agentResponse.body;

  const stream = new ReadableStream({
    async start(controller) {
      const reader = upstream.getReader();
      let buffer = "";
      let fullText = "";
      let doneEvent: Extract<StreamEvent, { type: "done" }> | null = null;
      let streamError: string | null = null;

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const parsed = parseSseChunk(buffer);
          buffer = parsed.rest;

          for (const event of parsed.events) {
            if (event.type === "token" && event.content) {
              fullText += event.content;
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify({ type: "token", content: event.content })}\n\n`),
              );
            } else if (event.type === "status" && event.content) {
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify({ type: "status", content: event.content })}\n\n`),
              );
            } else if (event.type === "error" && event.message) {
              streamError = event.message;
              controller.enqueue(
                encoder.encode(`data: ${JSON.stringify({ type: "error", message: event.message })}\n\n`),
              );
            } else if (event.type === "done") {
              doneEvent = event;
            }
          }
        }

        if (streamError) {
          controller.close();
          return;
        }

        const finalMessage =
          extractFinalText(doneEvent, fullText) ||
          "No recibí respuesta del modelo. Verifica que vLLM esté activo y responda correctamente.";
        const modelUsed =
          (typeof doneEvent?.model_used === "string" && doneEvent.model_used) || undefined;
        const toolCalls = doneEvent?.tool_calls;
        const files = doneEvent?.files ?? [];

        if (toolCalls?.length) {
          for (const toolCall of toolCalls) {
            await prisma.message.create({
              data: {
                conversationId: convId,
                role: MessageRole.TOOL,
                content: toolCall.result,
                toolName: toolCall.name,
                metadata: { arguments: toolCall.arguments } as Prisma.InputJsonValue,
              },
            });
          }
        }

        const assistantMessage = await prisma.message.create({
          data: {
            conversationId: convId,
            role: MessageRole.ASSISTANT,
            content: finalMessage,
            metadata: {
              ...(modelUsed ? { model_used: modelUsed } : {}),
              files,
            } as Prisma.InputJsonValue,
          },
        });

        await prisma.conversation.update({
          where: { id: convId },
          data: { updatedAt: new Date() },
        });

        controller.enqueue(
          encoder.encode(
            `data: ${JSON.stringify({
              type: "done",
              conversationId: convId,
              message: assistantMessage,
              model_used: modelUsed,
            })}\n\n`,
          ),
        );
        controller.close();
      } catch (streamError) {
        controller.error(streamError);
      }
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
    },
  });
}
