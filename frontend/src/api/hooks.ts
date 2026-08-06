import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { analyses, configOptions, farmers, fields, health, irrigations } from "./resources";
import type {
  AnalysisRequest,
  FarmerCreate,
  FieldCreate,
  FieldUpdate,
  IrrigationEventCreate,
} from "../types/api";

export function useHealth() {
  return useQuery({ queryKey: ["health"], queryFn: ({ signal }) => health.get(signal) });
}

export function useConfigOptions() {
  return useQuery({
    queryKey: ["config-options"],
    queryFn: ({ signal }) => configOptions.get(signal),
    staleTime: Infinity,
  });
}

export function useFarmer(farmerId: number | null) {
  return useQuery({
    queryKey: ["farmer", farmerId],
    queryFn: ({ signal }) => farmers.get(farmerId as number, signal),
    enabled: farmerId !== null,
  });
}

export function useCreateFarmer() {
  return useMutation({
    mutationFn: (body: FarmerCreate) => farmers.create(body),
  });
}

export function useFindFarmerByPhone() {
  return useMutation({
    mutationFn: (phone: string) => farmers.getByPhone(phone),
  });
}

export function useFields(farmerId: number | null) {
  return useQuery({
    queryKey: ["fields", farmerId],
    queryFn: ({ signal }) => fields.list(farmerId as number, signal),
    enabled: farmerId !== null,
  });
}

export function useField(fieldId: number | null) {
  return useQuery({
    queryKey: ["field", fieldId],
    queryFn: ({ signal }) => fields.get(fieldId as number, signal),
    enabled: fieldId !== null,
  });
}

export function useCreateField() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: FieldCreate) => fields.create(body),
    onSuccess: (created) => {
      void queryClient.invalidateQueries({ queryKey: ["fields", created.farmer_id] });
    },
  });
}

export function useUpdateField(fieldId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: FieldUpdate) => fields.update(fieldId, body),
    onSuccess: (updated) => {
      void queryClient.invalidateQueries({ queryKey: ["field", fieldId] });
      void queryClient.invalidateQueries({ queryKey: ["fields", updated.farmer_id] });
    },
  });
}

export function useDeleteField(farmerId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (fieldId: number) => fields.remove(fieldId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["fields", farmerId] });
    },
  });
}

export function useIrrigationEvents(fieldId: number | null) {
  return useQuery({
    queryKey: ["irrigations", fieldId],
    queryFn: ({ signal }) => irrigations.list(fieldId as number, signal),
    enabled: fieldId !== null,
  });
}

export function useCreateIrrigationEvent(fieldId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: IrrigationEventCreate) => irrigations.create(fieldId, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["irrigations", fieldId] });
    },
  });
}

export function useAnalyses(fieldId: number | null) {
  return useQuery({
    queryKey: ["analyses", fieldId],
    queryFn: ({ signal }) => analyses.list(fieldId as number, signal),
    enabled: fieldId !== null,
  });
}

export function useAnalysis(fieldId: number | null, analysisId: number | null) {
  return useQuery({
    queryKey: ["analysis", fieldId, analysisId],
    queryFn: ({ signal }) => analyses.get(fieldId as number, analysisId as number, signal),
    enabled: fieldId !== null && analysisId !== null,
  });
}

export function useRunAnalysis(fieldId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ body, signal }: { body: AnalysisRequest; signal?: AbortSignal }) =>
      analyses.create(fieldId, body, signal),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["analyses", fieldId] });
    },
  });
}

export function useSatelliteTimeseries(fieldId: number | null) {
  return useQuery({
    queryKey: ["satellite-timeseries", fieldId],
    queryFn: ({ signal }) => analyses.satelliteTimeseries(fieldId as number, signal),
    enabled: fieldId !== null,
  });
}

export function useWeather(fieldId: number | null) {
  return useQuery({
    queryKey: ["weather", fieldId],
    queryFn: ({ signal }) => analyses.weather(fieldId as number, signal),
    enabled: fieldId !== null,
  });
}
