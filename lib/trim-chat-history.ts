import { MessageRole } from "@/generated/prisma/client";

const MAX_MESSAGE_CHARS = 2500;
const DEFAULT_PER_ROLE = 2;

function truncateContent(text: string, maxChars = MAX_MESSAGE_CHARS): string {
  if (text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(0, maxChars - 14))}...[truncado]`;
}

/** Últimos N mensajes de usuario y N del asistente (sin TOOL), con contenido truncado. */
export function trimChatHistory<
  T extends { role: MessageRole | string; content?: string | null },
>(messages: T[], perRole = DEFAULT_PER_ROLE): T[] {
  let users = 0;
  let assistants = 0;
  const kept: T[] = [];

  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    const role = String(message.role).toUpperCase();

    if (role === "USER") {
      if (users >= perRole) continue;
      users += 1;
    } else if (role === "ASSISTANT") {
      if (assistants >= perRole) continue;
      assistants += 1;
    } else {
      continue;
    }

    const content = typeof message.content === "string" ? message.content : "";
    kept.unshift({
      ...message,
      content: truncateContent(content),
    });
  }

  return kept;
}
