#!/usr/bin/env node
// Orchestrates `make e2e`: install Chromium if needed, start the compose
// stack only if it isn't already running, run the Playwright suite, and
// leave the stack exactly as it was found. See docs/testing.md and
// e2e/README.md for the contract this implements.
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const APP_PORT = process.env.APP_PORT ?? "8100";
const HEALTH_URL = `http://localhost:${APP_PORT}/health`;

// This script runs with cwd = e2e/ (per the Makefile's `cd e2e && ... node
// scripts/run.mjs`), but docker-compose.yaml lives at the repo root — one
// level up from this file.
const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");

function run(command, args, options = {}) {
  const result = spawnSync(command, args, { stdio: "inherit", shell: process.platform === "win32", ...options });
  return result.status ?? 1;
}

function runCompose(args) {
  return run("docker", ["compose", ...args], { cwd: repoRoot });
}

async function isStackUp() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 1000);
    const res = await fetch(HEALTH_URL, { signal: controller.signal });
    clearTimeout(timeout);
    return res.status === 200;
  } catch {
    return false;
  }
}

async function main() {
  // 1. Install Chromium (Playwright's own installer no-ops when the right
  // version is already present).
  const installStatus = run("npx", ["playwright", "install", "chromium"]);
  if (installStatus !== 0) {
    process.exit(installStatus);
  }

  // 2. Stack detection.
  let startedStack = false;
  const up = await isStackUp();
  if (!up) {
    const upStatus = runCompose(["up", "-d", "--build", "--wait"]);
    if (upStatus !== 0) {
      // 3. Partial creation cleanup, then exit non-zero without testing.
      runCompose(["down", "-v"]);
      process.exit(upStatus);
    }
    startedStack = true;
  }

  // 4. Run the suite, capturing its exit code.
  const testStatus = run("npx", ["playwright", "test"]);

  // 5. Symmetric teardown — only if this script started the stack.
  if (startedStack) {
    runCompose(["down", "-v"]);
  }

  // 6. Exit with the test's exit code, never masked by teardown.
  process.exit(testStatus);
}

main();
