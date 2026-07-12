import { NextResponse } from "next/server";
import { getAgentApiUrl } from "@/lib/env";
import { requireAuth } from "@/lib/require-auth";

export async function GET(
  _request: Request,
  context: { params: Promise<{ id: string }> },
) {
  const { error } = await requireAuth();
  if (error) return error;

  const { id } = await context.params;
  const agentApiUrl = getAgentApiUrl();

  try {
    const response = await fetch(`${agentApiUrl}/jobs/${id}`, {
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });

    if (!response.ok) {
      const detail = await response.text();
      return NextResponse.json(
        { error: "No se pudo consultar el job", detail, agentApiUrl },
        { status: response.status === 404 ? 404 : 502 },
      );
    }

    return NextResponse.json(await response.json());
  } catch (jobError) {
    return NextResponse.json(
      {
        error: "FastAPI no respondió al consultar el job",
        detail: jobError instanceof Error ? jobError.message : "Error desconocido",
        agentApiUrl,
      },
      { status: 502 },
    );
  }
}
