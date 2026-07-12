import { NextResponse } from "next/server";
import { getAgentApiUrl } from "@/lib/env";
import { requireAuth } from "@/lib/require-auth";

export async function GET() {
  const { error } = await requireAuth();
  if (error) return error;

  const agentApiUrl = getAgentApiUrl();

  try {
    const response = await fetch(`${agentApiUrl}/health`, {
      signal: AbortSignal.timeout(5_000),
      cache: "no-store",
    });
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
