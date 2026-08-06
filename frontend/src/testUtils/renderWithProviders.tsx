import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";

import { ActiveFarmerProvider } from "../features/farmer/ActiveFarmerContext";
import { Layout } from "../components/layout/Layout";
import { WithActiveFarmer } from "./WithActiveFarmer";

export function testQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

/**
 * Renders a page at a given route, with or without the shared Layout shell
 * (header nav + persistent disclaimer footer), inside a MemoryRouter so
 * tests never depend on real browser history or a real backend.
 */
export function renderAtRoute(
  element: ReactElement,
  {
    path = "/",
    route = path,
    withLayout = true,
    client = testQueryClient(),
  }: { path?: string; route?: string; withLayout?: boolean; client?: QueryClient } = {}
) {
  const routeElement = <Route path={path} element={element} />;

  return render(
    <QueryClientProvider client={client}>
      <ActiveFarmerProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            {withLayout ? <Route element={<Layout />}>{routeElement}</Route> : routeElement}
          </Routes>
        </MemoryRouter>
      </ActiveFarmerProvider>
    </QueryClientProvider>
  );
}

/** Like renderAtRoute, but also sets the active farmer id via the real
 * context setter before rendering children (see WithActiveFarmer). */
export function renderWithActiveFarmer(
  element: ReactElement,
  {
    farmerId,
    path = "/",
    route = path,
    withLayout = true,
    client = testQueryClient(),
  }: {
    farmerId: number;
    path?: string;
    route?: string;
    withLayout?: boolean;
    client?: QueryClient;
  }
) {
  const routeElement = (
    <Route path={path} element={<WithActiveFarmer farmerId={farmerId}>{element}</WithActiveFarmer>} />
  );

  return render(
    <QueryClientProvider client={client}>
      <ActiveFarmerProvider>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            {withLayout ? <Route element={<Layout />}>{routeElement}</Route> : routeElement}
          </Routes>
        </MemoryRouter>
      </ActiveFarmerProvider>
    </QueryClientProvider>
  );
}
