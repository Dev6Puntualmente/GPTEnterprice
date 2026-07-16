import fs from "node:fs/promises";
import path from "node:path";
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

const LOCAL_STORAGE_DIR = path.join(process.cwd(), "backend", "storage");

function contentTypeForFilename(filename: string, fallback?: string | null): string {
  if (fallback) return fallback;
  const ext = filename.includes(".") ? filename.split(".").pop()!.toLowerCase() : "";
  return MEDIA_TYPES[ext] ?? "application/octet-stream";
}

function fileResponse(
  body: ArrayBuffer | Buffer,
  filename: string,
  contentType?: string | null,
) {
  const bytes = body instanceof Buffer ? new Uint8Array(body) : body;
  return new NextResponse(bytes, {
    status: 200,
    headers: {
      "Content-Type": contentTypeForFilename(filename, contentType),
      "Content-Disposition": `attachment; filename="${filename}"`,
      "Cache-Control": "private, max-age=3600",
    },
  });
}

async function readLocalStorageFile(filename: string): Promise<Buffer | null> {
  const filePath = path.join(LOCAL_STORAGE_DIR, filename);
  const resolvedStorage = path.resolve(LOCAL_STORAGE_DIR);
  const resolvedFile = path.resolve(filePath);
  if (
    resolvedFile !== resolvedStorage &&
    !resolvedFile.startsWith(`${resolvedStorage}${path.sep}`)
  ) {
    return null;
  }

  try {
    return await fs.readFile(resolvedFile);
  } catch {
    return null;
  }
}

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

  try {
    const upstream = await fetch(agentUrl, { cache: "no-store" });
    if (upstream.ok) {
      const buffer = await upstream.arrayBuffer();
      return fileResponse(
        buffer,
        safeName,
        upstream.headers.get("content-type"),
      );
    }

    if (upstream.status !== 404) {
      const detail = await upstream.text().catch(() => "");
      console.error(
        `[api/files] FastAPI ${upstream.status} para ${safeName}: ${detail.slice(0, 200)}`,
      );
    }
  } catch (fetchError) {
    const detail = fetchError instanceof Error ? fetchError.message : "Error de red";
    console.error(`[api/files] proxy falló para ${safeName} (${agentUrl}): ${detail}`);
  }

  const local = await readLocalStorageFile(safeName);
  if (local) {
    console.warn(`[api/files] sirviendo ${safeName} desde backend/storage (fallback local)`);
    return fileResponse(local, safeName);
  }

  return NextResponse.json(
    {
      error: "Archivo no encontrado",
      detail: `No disponible en ${getAgentApiUrl()} ni en ${LOCAL_STORAGE_DIR}`,
    },
    { status: 404 },
  );
}
