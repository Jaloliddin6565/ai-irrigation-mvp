import { apiDelete, apiGet, apiPatch, apiPost } from "./client";
import type {
  AnalysisListResponse,
  AnalysisRequest,
  AnalysisResponse,
  ConfigOptionsResponse,
  FarmerCreate,
  FarmerRead,
  FieldCreate,
  FieldListResponse,
  FieldRead,
  FieldUpdate,
  HealthResponse,
  IrrigationEventCreate,
  IrrigationEventListResponse,
  SatelliteTimeseriesResponse,
  WeatherResponse,
} from "../types/api";

export const health = {
  get: (signal?: AbortSignal) => apiGet<HealthResponse>("/health", { signal }),
};

export const configOptions = {
  get: (signal?: AbortSignal) => apiGet<ConfigOptionsResponse>("/api/config/options", { signal }),
};

export const farmers = {
  create: (body: FarmerCreate) => apiPost<FarmerRead>("/api/farmers", body),
  get: (farmerId: number, signal?: AbortSignal) =>
    apiGet<FarmerRead>(`/api/farmers/${farmerId}`, { signal }),
  getByPhone: (phone: string, signal?: AbortSignal) =>
    apiGet<FarmerRead>("/api/farmers", { query: { phone }, signal }),
};

export const fields = {
  create: (body: FieldCreate) => apiPost<FieldRead>("/api/fields", body),
  list: (farmerId: number, signal?: AbortSignal) =>
    apiGet<FieldListResponse>("/api/fields", { query: { farmer_id: farmerId }, signal }),
  get: (fieldId: number, signal?: AbortSignal) =>
    apiGet<FieldRead>(`/api/fields/${fieldId}`, { signal }),
  update: (fieldId: number, body: FieldUpdate) =>
    apiPatch<FieldRead>(`/api/fields/${fieldId}`, body),
  remove: (fieldId: number) => apiDelete<void>(`/api/fields/${fieldId}`),
};

export const irrigations = {
  create: (fieldId: number, body: IrrigationEventCreate) =>
    apiPost(`/api/fields/${fieldId}/irrigations`, body) as Promise<
      IrrigationEventListResponse["items"][number]
    >,
  list: (fieldId: number, signal?: AbortSignal) =>
    apiGet<IrrigationEventListResponse>(`/api/fields/${fieldId}/irrigations`, {
      query: { limit: 200 },
      signal,
    }),
};

export const analyses = {
  create: (fieldId: number, body: AnalysisRequest, signal?: AbortSignal) =>
    apiPost<AnalysisResponse>(`/api/fields/${fieldId}/analyze`, body, { signal }),
  list: (fieldId: number, signal?: AbortSignal) =>
    apiGet<AnalysisListResponse>(`/api/fields/${fieldId}/analyses`, {
      query: { limit: 50 },
      signal,
    }),
  get: (fieldId: number, analysisId: number, signal?: AbortSignal) =>
    apiGet<AnalysisResponse>(`/api/fields/${fieldId}/analyses/${analysisId}`, { signal }),
  satelliteTimeseries: (fieldId: number, signal?: AbortSignal) =>
    apiGet<SatelliteTimeseriesResponse>(`/api/fields/${fieldId}/satellite-timeseries`, {
      signal,
    }),
  weather: (fieldId: number, signal?: AbortSignal) =>
    apiGet<WeatherResponse>(`/api/fields/${fieldId}/weather`, { signal }),
};
