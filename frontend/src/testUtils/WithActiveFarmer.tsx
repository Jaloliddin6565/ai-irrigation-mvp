import { useEffect, type ReactNode } from "react";

import { useActiveFarmer } from "../features/farmer/ActiveFarmerContext";

/** Test helper: sets the active farmer id via the real context setter
 * (which tolerates an unavailable localStorage) rather than writing to
 * localStorage directly, which is not reliably available in this test
 * environment. Must be rendered inside an ActiveFarmerProvider. */
export function WithActiveFarmer({
  farmerId,
  children,
}: {
  farmerId: number;
  children: ReactNode;
}) {
  const { activeFarmerId, setActiveFarmerId } = useActiveFarmer();

  useEffect(() => {
    if (activeFarmerId !== farmerId) {
      setActiveFarmerId(farmerId);
    }
  }, [activeFarmerId, farmerId, setActiveFarmerId]);

  if (activeFarmerId !== farmerId) return null;
  return <>{children}</>;
}
