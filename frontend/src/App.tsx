import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import "./App.css";
import { Loading } from "./components/feedback/Loading";
import { Layout } from "./components/layout/Layout";
import { ActiveFarmerProvider } from "./features/farmer/ActiveFarmerContext";
import { RequireFarmer } from "./features/farmer/RequireFarmer";
import { LandingPage } from "./pages/LandingPage";

// Route-level code splitting: pages that pull in Leaflet/Geoman (map) or
// Recharts (charts) are the bulk of the production bundle (see
// docs/architecture.md "Frontend bundle"). Splitting them means a farmer
// who only registers and browses the dashboard never downloads mapping or
// charting code at all.
const FarmerRegisterPage = lazy(() =>
  import("./pages/FarmerRegisterPage").then((m) => ({ default: m.FarmerRegisterPage }))
);
const FarmerSelectPage = lazy(() =>
  import("./pages/FarmerSelectPage").then((m) => ({ default: m.FarmerSelectPage }))
);
const MethodologyPage = lazy(() =>
  import("./pages/MethodologyPage").then((m) => ({ default: m.MethodologyPage }))
);
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((m) => ({ default: m.DashboardPage }))
);
const FieldNewPage = lazy(() =>
  import("./pages/FieldNewPage").then((m) => ({ default: m.FieldNewPage }))
);
const FieldEditPage = lazy(() =>
  import("./pages/FieldEditPage").then((m) => ({ default: m.FieldEditPage }))
);
const FieldDetailsPage = lazy(() =>
  import("./pages/FieldDetailsPage").then((m) => ({ default: m.FieldDetailsPage }))
);
const IrrigationNewPage = lazy(() =>
  import("./pages/IrrigationNewPage").then((m) => ({ default: m.IrrigationNewPage }))
);
const AnalysisLatestPage = lazy(() =>
  import("./pages/AnalysisLatestPage").then((m) => ({ default: m.AnalysisLatestPage }))
);
const AnalysisHistoryPage = lazy(() =>
  import("./pages/AnalysisHistoryPage").then((m) => ({ default: m.AnalysisHistoryPage }))
);
const AnalysisDetailPage = lazy(() =>
  import("./pages/AnalysisDetailPage").then((m) => ({ default: m.AnalysisDetailPage }))
);
const NotFoundPage = lazy(() =>
  import("./pages/NotFoundPage").then((m) => ({ default: m.NotFoundPage }))
);

export function App() {
  return (
    <ActiveFarmerProvider>
      <BrowserRouter>
        <Suspense fallback={<Loading />}>
          <Routes>
            <Route element={<Layout />}>
              <Route path="/" element={<LandingPage />} />
              <Route path="/farmers/new" element={<FarmerRegisterPage />} />
              <Route path="/farmers/select" element={<FarmerSelectPage />} />
              <Route path="/methodology" element={<MethodologyPage />} />

              <Route element={<RequireFarmer />}>
                <Route path="/dashboard" element={<DashboardPage />} />
                <Route path="/fields/new" element={<FieldNewPage />} />
              </Route>

              <Route path="/fields/:fieldId" element={<FieldDetailsPage />} />
              <Route path="/fields/:fieldId/edit" element={<FieldEditPage />} />
              <Route path="/fields/:fieldId/irrigations/new" element={<IrrigationNewPage />} />
              <Route path="/fields/:fieldId/analysis" element={<AnalysisLatestPage />} />
              <Route path="/fields/:fieldId/analyses" element={<AnalysisHistoryPage />} />
              <Route
                path="/fields/:fieldId/analyses/:analysisId"
                element={<AnalysisDetailPage />}
              />

              <Route path="/not-found" element={<NotFoundPage />} />
              <Route path="*" element={<NotFoundPage />} />
            </Route>
          </Routes>
        </Suspense>
      </BrowserRouter>
    </ActiveFarmerProvider>
  );
}
