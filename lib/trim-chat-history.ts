import { MessageRole } from "@/generated/prisma/client";

/** Últimos N mensajes de usuario y N del asistente (sin TOOL) para no exceder contexto del LLM. */
export function trimChatHistory<T extends { role: MessageRole | string }>(
  messages: T[],
  perRole = 3,
): T[] {
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

    kept.unshift(message);
  }

  return kept;
}
