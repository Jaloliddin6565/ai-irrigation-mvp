import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

import { describe, expect, it } from "vitest";

// Enforces CLAUDE.md rule 7 and the Phase 5 spec's frontend security
// requirements as an automated regression, not just a manual claim: no
// CDSE/Open-Meteo endpoint, credential, or bearer-token handling may ever
// live in frontend source — every external-data request must go through
// the backend.
const FORBIDDEN_PATTERNS: { label: string; pattern: RegExp }[] = [
  { label: "CDSE identity/token endpoint", pattern: /identity\.dataspace\.copernicus\.eu/i },
  { label: "Sentinel Hub endpoint", pattern: /services\.sentinel-hub\.com/i },
  { label: "Open-Meteo endpoint", pattern: /api\.open-meteo\.com/i },
  { label: "CDSE client id env var", pattern: /CDSE_CLIENT_ID/ },
  { label: "CDSE client secret env var", pattern: /CDSE_CLIENT_SECRET/ },
  { label: "bearer token literal handling", pattern: /Bearer \$\{/ },
  { label: "Authorization header assignment", pattern: /["']Authorization["']\s*:/ },
];

function listSourceFiles(dir: string): string[] {
  const entries = readdirSync(dir);
  const files: string[] = [];
  for (const entry of entries) {
    const fullPath = join(dir, entry);
    const stats = statSync(fullPath);
    if (stats.isDirectory()) {
      files.push(...listSourceFiles(fullPath));
      continue;
    }
    if (
      (entry.endsWith(".ts") || entry.endsWith(".tsx")) &&
      !entry.endsWith(".test.ts") &&
      !entry.endsWith(".test.tsx")
    ) {
      files.push(fullPath);
    }
  }
  return files;
}

describe("frontend source contains no external-provider secrets or direct calls", () => {
  it("has no forbidden pattern anywhere under src/", () => {
    const files = listSourceFiles(resolve(__dirname));

    const offenders: string[] = [];
    for (const file of files) {
      const content = readFileSync(file, "utf8");
      for (const { label, pattern } of FORBIDDEN_PATTERNS) {
        if (pattern.test(content)) {
          offenders.push(`${file}: ${label}`);
        }
      }
    }

    expect(offenders).toEqual([]);
  });

  it("declares no VITE_ environment variable that looks like a secret", () => {
    const viteEnvContent = readFileSync(resolve(__dirname, "vite-env.d.ts"), "utf8");
    expect(viteEnvContent).not.toMatch(/VITE_.*(SECRET|TOKEN|KEY|PASSWORD|CDSE)/i);
  });
});
