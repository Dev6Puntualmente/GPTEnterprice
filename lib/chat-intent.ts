const SPANISH_MONTHS: Record<string, number> = {
  enero: 1,
  febrero: 2,
  marzo: 3,
  abril: 4,
  mayo: 5,
  junio: 6,
  julio: 7,
  agosto: 8,
  septiembre: 9,
  setiembre: 9,
  octubre: 10,
  noviembre: 11,
  diciembre: 12,
};

const EXCEL_KEYWORDS = ["excel", "xlsx", "exportar", "reporte", "informe"];
const CALLS_KEYWORDS = ["llamada", "llamadas", "llmada", "llmadas", "calls"];

export type HeavyToolIntent = {
  tool: "reporte_llamadas_excel" | "generar_reporte_excel";
  label: string;
  args: Record<string, string>;
};

function iso(day: number, month: number, year: number): string {
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

function weekRange(reference = new Date()): [string, string] {
  const day = reference.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  const start = new Date(reference);
  start.setDate(reference.getDate() + mondayOffset);
  const end = new Date(start);
  end.setDate(start.getDate() + 6);
  return [start.toISOString().slice(0, 10), end.toISOString().slice(0, 10)];
}

export function extractDateRange(text: string): [string, string] | null {
  const lowered = text.toLowerCase();

  const isoDates = text.match(/\b(\d{4}-\d{2}-\d{2})\b/g);
  if (isoDates && isoDates.length >= 2) return [isoDates[0], isoDates[1]];
  if (isoDates?.length === 1) return [isoDates[0], isoDates[0]];

  const compactRange = lowered.match(
    /(?:del\s+)?(\d{1,2})\s+al\s+(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?:\s+(?:de(?:l|\s)?|dl))?\s*(\d{4})/i,
  );
  if (compactRange) {
    const [, startDay, endDay, monthName, year] = compactRange;
    const month = SPANISH_MONTHS[monthName.toLowerCase()];
    return [iso(Number(startDay), month, Number(year)), iso(Number(endDay), month, Number(year))];
  }

  const spanishDates: string[] = [];
  const dateRegex =
    /(\d{1,2})\s+de\s+(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)(?:\s+(?:de(?:l|\s)?|dl))?\s*(\d{4})/gi;
  let match: RegExpExecArray | null;
  while ((match = dateRegex.exec(text)) !== null) {
    const month = SPANISH_MONTHS[match[2].toLowerCase()];
    spanishDates.push(iso(Number(match[1]), month, Number(match[3])));
  }

  if (spanishDates.length >= 2) return [spanishDates[0], spanishDates[1]];
  if (spanishDates.length === 1) return [spanishDates[0], spanishDates[0]];

  if (lowered.includes("esta semana") || lowered.includes("de esta semana")) {
    return weekRange();
  }

  return null;
}

export function buildDateContext(now = new Date()): string {
  const formatted = now.toLocaleString("es-CO", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/Bogota",
  });
  const [weekStart, weekEnd] = weekRange(now);
  return [
    `Fecha y hora actual: ${formatted} (America/Bogota).`,
    `ISO hoy: ${now.toISOString().slice(0, 10)}.`,
    `Esta semana (lun-dom): ${weekStart} → ${weekEnd}.`,
    "NUNCA inventes URLs de descarga ni digas que un archivo ya está listo si el sistema no lo confirmó.",
    "Si el usuario pide Excel, el backend generará el archivo en segundo plano.",
  ].join("\n");
}

function userMessages(messages: Array<{ role: string; content: string }>) {
  return messages.filter((message) => message.role === "USER" || message.role === "user");
}

export function detectHeavyToolIntent(
  messages: Array<{ role: string; content: string }>,
  availableTools: string[],
): HeavyToolIntent | null {
  const allowed = new Set(availableTools);
  const users = userMessages(messages);
  if (users.length === 0) return null;

  const lastUserText = users[users.length - 1]?.content ?? "";
  const recentUserText = users
    .slice(-4)
    .map((message) => message.content)
    .join("\n");
  const lastLower = lastUserText.toLowerCase();
  const recentLower = recentUserText.toLowerCase();

  const wantsExcelNow = EXCEL_KEYWORDS.some((keyword) => lastLower.includes(keyword));
  const wantsCallsNow = CALLS_KEYWORDS.some((keyword) => lastLower.includes(keyword));
  const wantsExcelRecent = EXCEL_KEYWORDS.some((keyword) => recentLower.includes(keyword));
  const wantsCallsRecent = CALLS_KEYWORDS.some((keyword) => recentLower.includes(keyword));

  const confirmingDatesOnly =
    !wantsExcelNow &&
    !wantsCallsNow &&
    Boolean(extractDateRange(lastUserText)) &&
    wantsExcelRecent &&
    wantsCallsRecent;

  if (!allowed.has("reporte_llamadas_excel")) return null;
  if (!((wantsExcelNow && wantsCallsNow) || confirmingDatesOnly)) return null;

  const dateRange = extractDateRange(recentUserText);
  if (!dateRange) return null;

  return {
    tool: "reporte_llamadas_excel",
    label: "Reporte de llamadas en Excel",
    args: { fecha_inicio: dateRange[0], fecha_fin: dateRange[1] },
  };
}
