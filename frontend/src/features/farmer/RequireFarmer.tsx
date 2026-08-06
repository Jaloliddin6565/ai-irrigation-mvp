import { Navigate, Outlet } from "react-router-dom";

import { useActiveFarmer } from "./ActiveFarmerContext";

/** Redirects to farmer selection when no active farmer is set. This is a
 * UX convenience, not a security boundary — see ActiveFarmerContext. */
export function RequireFarmer() {
  const { activeFarmerId } = useActiveFarmer();

  if (activeFarmerId === null) {
    return <Navigate to="/farmers/select" replace />;
  }

  return <Outlet />;
}
