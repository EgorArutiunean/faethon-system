import { stopE2eEnvironment } from "./docker-environment";

export default function globalTeardown() {
  stopE2eEnvironment();
}
