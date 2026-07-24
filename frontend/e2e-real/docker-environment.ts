import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";

const currentDirectory = fileURLToPath(new URL(".", import.meta.url));
const projectRoot = resolve(currentDirectory, "..", "..");
const composeFile = resolve(projectRoot, "docker-compose.e2e.yml");
const composeArgs = ["compose", "-p", "buy-modern-e2e", "-f", composeFile];
const backendImage = "buy-modern-backend";

function dockerCompose(...args: string[]) {
  execFileSync("docker", [...composeArgs, ...args], {
    cwd: projectRoot,
    stdio: "inherit",
  });
}

export function stopE2eEnvironment() {
  dockerCompose("down", "--volumes", "--remove-orphans");
}

export default function startE2eEnvironment() {
  stopE2eEnvironment();
  try {
    execFileSync("docker", ["image", "inspect", backendImage], { stdio: "ignore" });
  } catch {
    execFileSync("docker", ["compose", "-f", resolve(projectRoot, "docker-compose.yml"), "build", "backend"], {
      cwd: projectRoot,
      stdio: "inherit",
    });
  }
  dockerCompose("up", "--detach", "--wait");
}
