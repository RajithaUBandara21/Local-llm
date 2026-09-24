"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import {
  ApiError,
  changeActiveModel,
  getActiveModelSettings,
  getInstalledModels,
  setActiveTemperature,
} from "./api";

interface ModelSettingsContextValue {
  models: string[];
  modelsLoading: boolean;
  modelsError: string | null;
  retryModels: () => void;
  activeModel: string;
  activeTemperature: number;
  saving: boolean;
  saveError: string | null;
  applySettings: (model: string, temperature: number) => void;
}

const ModelSettingsContext = createContext<ModelSettingsContextValue | null>(null);

export function ModelSettingsProvider({ children }: Readonly<{ children: ReactNode }>) {
  const [models, setModels] = useState<string[]>([]);
  const [modelsLoading, setModelsLoading] = useState(true);
  const [modelsError, setModelsError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const [activeModel, setActiveModel] = useState("");
  const [activeTemperature, setActiveTemperatureState] = useState(0.7);

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getInstalledModels(), getActiveModelSettings()])
      .then(([installed, active]) => {
        if (cancelled) return;
        setModels(installed.models);
        setActiveModel(active.active_model);
        setActiveTemperatureState(active.active_temperature);
        setModelsError(null);
      })
      .catch((err) => {
        if (cancelled) return;
        setModelsError(
          err instanceof ApiError ? err.message : "Could not load models from Ollama."
        );
      })
      .finally(() => {
        if (!cancelled) setModelsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [reloadToken]);

  const retryModels = useCallback(() => {
    setModelsLoading(true);
    setReloadToken((t) => t + 1);
  }, []);

  const applySettings = useCallback(
    (model: string, temperature: number) => {
      setSaving(true);
      setSaveError(null);
      const modelChanged = model !== activeModel;
      const temperatureChanged = temperature !== activeTemperature;

      Promise.all([
        modelChanged ? changeActiveModel(model) : Promise.resolve(null),
        temperatureChanged ? setActiveTemperature(temperature) : Promise.resolve(null),
      ])
        .then(() => {
          setActiveModel(model);
          setActiveTemperatureState(temperature);
        })
        .catch((err) => {
          setSaveError(
            err instanceof ApiError ? err.message : "Could not save the model settings."
          );
        })
        .finally(() => {
          setSaving(false);
        });
    },
    [activeModel, activeTemperature]
  );

  const value = useMemo(
    () => ({
      models,
      modelsLoading,
      modelsError,
      retryModels,
      activeModel,
      activeTemperature,
      saving,
      saveError,
      applySettings,
    }),
    [
      models,
      modelsLoading,
      modelsError,
      retryModels,
      activeModel,
      activeTemperature,
      saving,
      saveError,
      applySettings,
    ]
  );

  return (
    <ModelSettingsContext.Provider value={value}>{children}</ModelSettingsContext.Provider>
  );
}

export function useModelSettings(): ModelSettingsContextValue {
  const ctx = useContext(ModelSettingsContext);
  if (!ctx) {
    throw new Error("useModelSettings must be used within a ModelSettingsProvider");
  }
  return ctx;
}
