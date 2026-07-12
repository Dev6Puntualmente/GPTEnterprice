import "dotenv/config";
import { prisma } from "../lib/prisma";
import { getAgentApiUrl, getHfToken } from "../lib/env";
import { resolveUserLlmEndpoint } from "../lib/server-config-access";

async function main() {
  const admin = await prisma.user.findFirst({
    where: { documentId: "1000000001" },
  });
  if (!admin) throw new Error("Admin not found");

  const project = await prisma.project.findFirst({
    where: { id: "demo-salescloser", ownerId: admin.id },
    include: { tools: { where: { isActive: true } } },
  });
  if (!project) throw new Error("Project not found");

  const llm = await resolveUserLlmEndpoint(admin.id);
  const agentApiUrl = getAgentApiUrl();
  const tools = project.tools.map((tool) => ({
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

  const contextBlock = project.contextJson
    ? `\n\nContexto del proyecto:\n${JSON.stringify(project.contextJson, null, 2)}`
    : "";

  const response = await fetch(`${agentApiUrl}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: AbortSignal.timeout(90_000),
    body: JSON.stringify({
      system_prompt: `${project.systemPrompt}${contextBlock}`,
      messages: [{ role: "user", content: "hola" }],
      tools,
      vllm: llm
        ? {
            base_url: llm.baseUrl,
            model: llm.modelName,
            api_key: llm.apiKey ?? getHfToken() ?? null,
          }
        : null,
    }),
  });

  console.log("status:", response.status);
  console.log("body:", await response.text());
  await prisma.$disconnect();
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
