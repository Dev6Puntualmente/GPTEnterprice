import { NextResponse } from "next/server";
import { requireAuth } from "@/lib/require-auth";
import { getAgentApiUrl } from "@/lib/env";

const MEDIA_TYPES: Record<string, string> = {
  pdf: "application/pdf",
  pptx: "application/vnd.openxmlformats-officedocument.presentationml.presentation",
  xlsx: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  png: "image/png",
  jpg: "image/jpeg",
  jpeg: "image/jpeg",
  svg: "image/svg+xml",
};

export async function GET(
  _request: Request,
  context: { params: Promise<{ filename: string }> },
) {
  const { session, error } = await requireAuth();
  if (error) return error;

  void session;

  const { filename: rawName } = await context.params;
  const safeName = rawName.replace(/[/\\]/g, "").split("?")[0];
  if (!safeName || safeName.includes("..")) {
    return NextResponse.json({ error: "Nombre de archivo inválido" }, { status: 400 });
  }

  const agentUrl = `${getAgentApiUrl()}/files/${encodeURIComponent(safeName)}`;
  let upstream: Response;
  try {
    upstream = await fetch(agentUrl, { cache: "no-store" });
  } catch (fetchError) {
    const detail = fetchError instanceof Error ? fetchError.message : "Error de red";
    return NextResponse.json(
      { error: "No se pudo obtener el archivo", detail },
      { status: 502 },
    );
  }

  if (!upstream.ok) {
    const detail = await upstream.text().catch(() => "");
    return NextResponse.json(
      { error: "Archivo no encontrado", detail: detail.slice(0, 200) },
      { status: upstream.status === 404 ? 404 : 502 },
    );
  }

  const ext = safeName.includes(".") ? safeName.split(".").pop()!.toLowerCase() : "";
  const contentType =
    upstream.headers.get("content-type") ??
    MEDIA_TYPES[ext] ??
    "application/octet-stream";

  const buffer = await upstream.arrayBuffer();

  return new NextResponse(buffer, {
    status: 200,
    headers: {
      "Content-Type": contentType,
      "Content-Disposition": `attachment; filename="${safeName}"`,
      "Cache-Control": "private, max-age=3600",
    },
  });
}
