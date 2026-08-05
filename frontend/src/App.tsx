import { BrowserRouter, Route, Routes } from "react-router-dom";

import "./App.css";
import { Layout } from "./components/layout/Layout";
import { ActiveFarmerProvider } from "./features/farmer/ActiveFarmerContext";
import { RequireFarmer } from "./features/farmer/RequireFarmer";
import { AnalysisDetailPage } from "./pages/AnalysisDetailPage";
import { AnalysisHistoryPage } from "./pages/AnalysisHistoryPage";
import { AnalysisLatestPage } from "./pages/AnalysisLatestPage";
import { DashboardPage } from "./pages/DashboardPage";
import { FarmerRegisterPage } from "./pages/FarmerRegisterPage";
import { FarmerSelectPage } from "./pages/FarmerSelectPage";
import { FieldDetailsPage } from "./pages/FieldDetailsPage";
import { FieldEditPage } from "./pages/FieldEditPage";
import { FieldNewPage } from "./pages/FieldNewPage";
import { IrrigationNewPage } from "./pages/IrrigationNewPage";
import { LandingPage } from "./pages/LandingPage";
import { MethodologyPage } from "./pages/MethodologyPage";
import { NotFoundPage } from "./pages/NotFoundPage";

export function App() {
  return (
    <ActiveFarmerProvider>
      <BrowserRouter>
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
            <Route path="/fields/:fieldId/analyses/:analysisId" element={<AnalysisDetailPage />} />

            <Route path="/not-found" element={<NotFoundPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ActiveFarmerProvider>
  );
}
