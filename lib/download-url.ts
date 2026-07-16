/** Convierte URLs del backend FastAPI a ruta relativa del front (mismo origen). */
export function normalizeDownloadUrl(url: string): string {
  const raw = (url || "").trim();
  if (!raw) return raw;

  if (raw.startsWith("/api/files/")) {
    return raw;
  }

  try {
    const parsed = new URL(raw, "http://local");
    const match = parsed.pathname.match(/\/files\/([^/]+)$/);
    if (match?.[1]) {
      return `/api/files/${decodeURIComponent(match[1])}`;
    }
  } catch {
    const tail = raw.split("/files/").pop();
    if (tail) {
      return `/api/files/${tail.split("?")[0]}`;
    }
  }

  return raw;
}

export function downloadFilenameFromUrl(url: string, fallback = "archivo"): string {
  const normalized = normalizeDownloadUrl(url);
  const name = normalized.split("/").pop() ?? fallback;
  return decodeURIComponent(name);
}

export function fileKindFromName(filename: string): "pdf" | "pptx" | "xlsx" | "image" | "other" {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  if (ext === "pdf") return "pdf";
  if (ext === "pptx" || ext === "ppt") return "pptx";
  if (ext === "xlsx" || ext === "xls") return "xlsx";
  if (["png", "jpg", "jpeg", "gif", "webp", "svg"].includes(ext)) return "image";
  return "other";
}
