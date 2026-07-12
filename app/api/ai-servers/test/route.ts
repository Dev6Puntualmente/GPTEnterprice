import { NextResponse } from "next/server";
import { getHfToken } from "@/lib/env";
import { requireAuth } from "@/lib/require-auth";

export async function POST(request: Request) {
  const { error } = await requireAuth();
  if (error) return error;

  const body = await request.json();
  const baseUrl = body.baseUrl?.replace(/\/$/, "");
  const apiKey = getHfToken() ?? "not-needed";

  if (!baseUrl) {
    return NextResponse.json({ error: "baseUrl es requerido" }, { status: 400 });
  }

  try {
    const response = await fetch(`${baseUrl}/models`, {
      headers: { Authorization: `Bearer ${apiKey}` },
      signal: AbortSignal.timeout(8000),
    });

    if (!response.ok) {
      return NextResponse.json(
        { ok: false, error: `HTTP ${response.status}` },
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
