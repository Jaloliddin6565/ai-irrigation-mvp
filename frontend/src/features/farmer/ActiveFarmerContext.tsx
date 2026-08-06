import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export const ACTIVE_FARMER_STORAGE_KEY = "ai-irrigation.activeFarmerId";
const STORAGE_KEY = ACTIVE_FARMER_STORAGE_KEY;

interface ActiveFarmerContextValue {
  activeFarmerId: number | null;
  setActiveFarmerId: (farmerId: number) => void;
  clearActiveFarmer: () => void;
}

const ActiveFarmerContext = createContext<ActiveFarmerContextValue | null>(null);

function readStoredFarmerId(): number | null {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  } catch {
    // localStorage may be unavailable (private browsing, disabled storage).
    return null;
  }
}

/**
 * Trusted-MVP active farmer selection. This is NOT authentication — it is a
 * client-side convenience so the UI knows which farmer is "current". Any
 * caller could set any farmer_id; the backend does not verify identity (see
 * CLAUDE.md rule 6 and docs/security.md).
 */
export function ActiveFarmerProvider({ children }: { children: ReactNode }) {
  const [activeFarmerId, setActiveFarmerIdState] = useState<number | null>(readStoredFarmerId);

  const setActiveFarmerId = useCallback((farmerId: number) => {
    setActiveFarmerIdState(farmerId);
    try {
      window.localStorage.setItem(STORAGE_KEY, String(farmerId));
    } catch {
      // ignore storage failures — in-memory state still works for this session
    }
  }, []);

  const clearActiveFarmer = useCallback(() => {
    setActiveFarmerIdState(null);
    try {
      window.localStorage.removeItem(STORAGE_KEY);
    } catch {
      // ignore storage failures
    }
  }, []);

  const value = useMemo(
    () => ({ activeFarmerId, setActiveFarmerId, clearActiveFarmer }),
    [activeFarmerId, setActiveFarmerId, clearActiveFarmer]
  );

  return <ActiveFarmerContext.Provider value={value}>{children}</ActiveFarmerContext.Provider>;
}

export function useActiveFarmer(): ActiveFarmerContextValue {
  const context = useContext(ActiveFarmerContext);
  if (!context) {
    throw new Error("useActiveFarmer must be used within an ActiveFarmerProvider");
  }
  return context;
}
