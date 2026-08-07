import { useCallback, useState } from "react";

export type GeolocationStatus =
  | "idle"
  | "locating"
  | "success"
  | "denied"
  | "unavailable"
  | "unsupported";

export interface GeolocationPositionResult {
  lat: number;
  lon: number;
  accuracyMeters: number | null;
}

interface GeolocationState {
  status: GeolocationStatus;
  position: GeolocationPositionResult | null;
}

/**
 * Wraps navigator.geolocation for the "Mening joylashuvim" map button.
 * Never throws and never blocks field creation — every failure path
 * (permission denied, GPS unavailable, insecure context, unsupported
 * browser) is surfaced as a status the caller renders as an inline Uzbek
 * message, not an exception.
 */
export function useGeolocation() {
  const [state, setState] = useState<GeolocationState>({ status: "idle", position: null });

  const locate = useCallback(() => {
    if (!window.isSecureContext || !navigator.geolocation) {
      setState({ status: "unsupported", position: null });
      return;
    }
    setState({ status: "locating", position: null });
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setState({
          status: "success",
          position: {
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            accuracyMeters: pos.coords.accuracy ?? null,
          },
        });
      },
      (error) => {
        setState({
          status: error.code === error.PERMISSION_DENIED ? "denied" : "unavailable",
          position: null,
        });
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 }
    );
  }, []);

  return { status: state.status, position: state.position, locate };
}
