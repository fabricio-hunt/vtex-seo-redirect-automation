#!/usr/bin/env node
/**
 * Starts the whole tool on the local machine with one command:
 *   1. the Python compute API (uvicorn, api/index.py) on 127.0.0.1:PYTHON_PORT
 *   2. the Next.js app on 127.0.0.1:WEB_PORT, once the API answers /api/health
 *
 * Usage: `npm run local` (production build) or `npm run local:dev` (next dev, hot reload).
 * Both servers bind to 127.0.0.1 only, so the tool is not reachable from the network.
 * Ctrl+C stops both.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const HOST = "127.0.0.1";
const PYTHON_PORT = Number(process.env.PYTHON_PORT || 8000);
const WEB_PORT = Number(process.env.WEB_PORT || 3000);
const HEALTH_TIMEOUT_MS = 60_000;
const isDev = process.argv.includes("--dev");

function resolvePython() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const candidates = [".venv", "venv"].flatMap((dir) => [
    path.join(ROOT, dir, "Scripts", "python.exe"),
    path.join(ROOT, dir, "bin", "python"),
  ]);
  return candidates.find((candidate) => existsSync(candidate)) ?? (process.platform === "win32" ? "python" : "python3");
}

function resolveNextBin() {
  return path.join(ROOT, "node_modules", "next", "dist", "bin", "next");
}

const children = [];

function start(label, command, args, env = {}) {
  const child = spawn(command, args, { cwd: ROOT, env: { ...process.env, ...env }, stdio: ["ignore", "pipe", "pipe"] });
  const prefix = (stream, target) =>
    stream.on("data", (chunk) => {
      for (const line of chunk.toString().split(/\r?\n/)) {
        if (line) target.write(`[${label}] ${line}\n`);
      }
    });
  prefix(child.stdout, process.stdout);
  prefix(child.stderr, process.stderr);
  child.on("exit", (code) => {
    console.error(`[${label}] exited with code ${code}`);
    shutdown(code ?? 1);
  });
  children.push(child);
  return child;
}

let shuttingDown = false;
function shutdown(code = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) {
    if (child.exitCode === null) child.kill();
  }
  process.exit(code);
}

async function waitForHealth(url) {
  const deadline = Date.now() + HEALTH_TIMEOUT_MS;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // Not listening yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`Python API did not become healthy at ${url} within ${HEALTH_TIMEOUT_MS / 1000}s.`);
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

const python = resolvePython();
const pythonApiBaseUrl = `http://${HOST}:${PYTHON_PORT}`;
console.log(`Starting compute API with ${python} ...`);
start("py", python, ["-m", "uvicorn", "api.index:app", "--host", HOST, "--port", String(PYTHON_PORT)]);

try {
  await waitForHealth(`${pythonApiBaseUrl}/api/health`);
} catch (error) {
  console.error(error.message);
  shutdown(1);
}

start("web", process.execPath, [resolveNextBin(), isDev ? "dev" : "start", "-H", HOST, "-p", String(WEB_PORT)], {
  PYTHON_API_BASE_URL: pythonApiBaseUrl,
});
console.log(`\nOpen http://localhost:${WEB_PORT}  (Ctrl+C to stop)\n`);
