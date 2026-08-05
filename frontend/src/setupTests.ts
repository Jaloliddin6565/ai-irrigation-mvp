import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";

// Best-effort: avoid leaking the active-farmer selection (or anything else)
// across test files sharing a worker/jsdom instance. localStorage itself is
// not reliably available in this environment (see ActiveFarmerContext's own
// try/catch), so this must never throw.
afterEach(() => {
  try {
    window.localStorage.clear();
  } catch {
    // ignore — localStorage unavailable in this environment
  }
});
