import { stopProductionE2eEnvironment } from "./prod-docker-environment";

export default function globalTeardown() {
  stopProductionE2eEnvironment();
}
