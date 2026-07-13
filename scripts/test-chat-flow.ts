import "dotenv/config";
import { prisma } from "../lib/prisma";
import { getAgentApiUrl } from "../lib/env";
import { resolveUserLlmEndpoint } from "../lib/server-config-access";

async function main() {
  const admin = await prisma.user.findFirst({
    where: { documentId: "1000000001" },
  });
  if (!admin) {
    console.error("Admin user not found");
    process.exit(1);
  }

  const llm = await resolveUserLlmEndpoint(admin.id);
  const agentApiUrl = getAgentApiUrl();

  console.log("agentApiUrl:", agentApiUrl);
  console.log("llm:", llm);

  const response = await fetch(`${agentApiUrl}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    signal: AbortSignal.timeout(90_000),
    body: JSON.stringify({
      system_prompt: "Eres un asistente util.",
      messages: [{ role: "user", content: "hola" }],
      tools: null,
      vllm: llm
        ? {
            base_url: llm.baseUrl,
            model: llm.modelName,
            api_key: llm.apiKey ?? null,
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
