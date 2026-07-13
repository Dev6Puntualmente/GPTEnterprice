import { NextResponse } from "next/server";
import { fetchAgent } from "@/lib/agent-fetch";
import { getAgentApiUrl } from "@/lib/env";
import { requireAuth } from "@/lib/require-auth";

export async function GET() {
  const { error } = await requireAuth();
  if (error) return error;

  const agentApiUrl = getAgentApiUrl();

  try {
    const response = await fetchAgent(
      `${agentApiUrl}/health`,
      { cache: "no-store" },
      { timeoutMs: 5_000, retries: 1, retryDelayMs: 400 },
    );
    const body = await response.text();

    const parsed = JSON.parse(body) as { status?: string; version?: string };

    return NextResponse.json({
      ok: response.ok,
      agentApiUrl,
      status: response.status,
      version: parsed.version ?? "unknown",
      jobsSupported: parsed.version === "agent-v2-jobs",
      body: parsed,
    });
  } catch (healthError) {
    return NextResponse.json(
      {
        ok: false,
        agentApiUrl,
        error:
          healthError instanceof Error
            ? healthError.message
            : "No se pudo contactar FastAPI",
      },
      { status: 502 },
    );
  }
}
