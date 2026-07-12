import { readFileSync, existsSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function loadEnvFile() {
  const envPath = resolve(root, ".env");
  if (!existsSync(envPath)) return {};

  const env = {};
  for (const line of readFileSync(envPath, "utf8").split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const separator = trimmed.indexOf("=");
    if (separator === -1) continue;

    const key = trimmed.slice(0, separator).trim();
    let value = trimmed.slice(separator + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    env[key] = value;
  }
  return env;
}

function buildDatabaseUrl(env) {
  if (env.DATABASE_URL) return env.DATABASE_URL;

  const { DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME } = env;
  if (!DB_USER || !DB_NAME) {
    throw new Error(
      "Define DATABASE_URL o DB_USER, DB_PASSWORD, DB_HOST, DB_PORT y DB_NAME en .env",
    );
  }

  const password = encodeURIComponent(DB_PASSWORD ?? "");
  const user = encodeURIComponent(DB_USER);
  const host = DB_HOST || "localhost";
  const port = DB_PORT || "5432";
  const schema = env.DB_SCHEMA || "gptenterprice";
  const base = `postgresql://${user}:${password}@${host}:${port}/${DB_NAME}`;
  return `${base}?schema=${encodeURIComponent(schema)}`;
}

const env = { ...process.env, ...loadEnvFile() };
env.DATABASE_URL = buildDatabaseUrl(env);

const args = process.argv.slice(2);
if (args.length === 0) {
  console.error("Uso: node scripts/with-database-url.mjs <comando...>");
  process.exit(1);
}

const command = args.join(" ");
const result = spawnSync(command, {
  stdio: "inherit",
  env,
  shell: true,
  cwd: root,
});

process.exit(result.status ?? 1);
