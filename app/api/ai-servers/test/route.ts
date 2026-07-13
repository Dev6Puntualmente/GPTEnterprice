import { NextResponse } from "next/server";
import { resolveEffectiveApiKey } from "@/lib/env";
import { requireAuth } from "@/lib/require-auth";
import { resolveUserLlmEndpoint } from "@/lib/server-config-access";

export async function POST(request: Request) {
  const { session, error } = await requireAuth();
  if (error) return error;

  const body = await request.json();
  const baseUrl = body.baseUrl?.replace(/\/$/, "");
  const apiKeyFromBody = typeof body.apiKey === "string" ? body.apiKey.trim() : "";

  if (!baseUrl) {
    return NextResponse.json({ error: "baseUrl es requerido" }, { status: 400 });
  }

  const endpoint = apiKeyFromBody ? null : await resolveUserLlmEndpoint(session.user.id);
  const apiKey = resolveEffectiveApiKey(apiKeyFromBody || endpoint?.apiKey);

  if (!apiKey) {
    return NextResponse.json(
      {
        ok: false,
        error:
          "Falta la API Key de vLLM. Configúrala en Ajustes → Proveedor de IA (debe coincidir con --api-key del servidor).",
      },
      { status: 401 },
    );
  }

  try {
    const response = await fetch(`${baseUrl}/models`, {
      headers: { Authorization: `Bearer ${apiKey}` },
      signal: AbortSignal.timeout(8000),
    });

    if (response.status === 401 || response.status === 403) {
      return NextResponse.json(
        {
          ok: false,
          error: "API Key de vLLM rechazada (HTTP 401). Debe coincidir con --api-key del servidor.",
        },
        { status: 401 },
      );
    }

    if (!response.ok) {
      return NextResponse.json(
        { ok: false, error: `vLLM respondió HTTP ${response.status}` },
        { status: 502 },
      );
    }

    const data = await response.json();
    return NextResponse.json({ ok: true, models: data.data ?? data });
  } catch (testError) {
    return NextResponse.json(
      {
        ok: false,
        error: testError instanceof Error ? testError.message : "No se pudo conectar",
      },
      { status: 502 },
    );
  }
}
