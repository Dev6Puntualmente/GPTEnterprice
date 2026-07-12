export function buildDatabaseUrl(): string {
  if (process.env.DATABASE_URL) {
    return process.env.DATABASE_URL;
  }

  const user = process.env.DB_USER;
  const password = process.env.DB_PASSWORD ?? "";
  const host = process.env.DB_HOST ?? "localhost";
  const port = process.env.DB_PORT ?? "5432";
  const name = process.env.DB_NAME;
  const schema = process.env.DB_SCHEMA ?? "gptenterprice";

  if (!user || !name) {
    throw new Error(
      "Configura DATABASE_URL o las variables DB_USER, DB_PASSWORD, DB_HOST, DB_PORT y DB_NAME",
    );
  }

  const base = `postgresql://${encodeURIComponent(user)}:${encodeURIComponent(password)}@${host}:${port}/${name}`;
  return `${base}?schema=${encodeURIComponent(schema)}`;
}
