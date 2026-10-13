import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const currentDirectory = fileURLToPath(new URL(".", import.meta.url));
const projectRoot = resolve(currentDirectory, "..", "..");
const composeFile = resolve(projectRoot, "docker-compose.prod-e2e.yml");
const composeArgs = ["compose", "-p", "buy-modern-prod-e2e", "-f", composeFile];

function dockerCompose(...args: string[]) {
  execFileSync("docker", [...composeArgs, ...args], {
    cwd: projectRoot,
    stdio: "inherit",
  });
}

export function stopProductionE2eEnvironment() {
  dockerCompose("down", "--volumes", "--remove-orphans");
}

export default function startProductionE2eEnvironment() {
  stopProductionE2eEnvironment();
  try {
    dockerCompose("build");
    dockerCompose("up", "--detach", "--wait");
  } catch (error) {
    stopProductionE2eEnvironment();
    throw error;
  }
}
