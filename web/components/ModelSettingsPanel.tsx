"use client";

import { useState } from "react";
import { useModelSettings } from "@/lib/model-settings-context";

const MIN_TEMPERATURE = 0;
const MAX_TEMPERATURE = 2;

export function ModelSettingsPanel() {
  const {
    models,
    modelsLoading,
    modelsError,
    retryModels,
    activeModel,
    activeTemperature,
    saving,
    saveError,
    applySettings,
  } = useModelSettings();

  // Edits start out unset and fall back to the active settings until the
  // user picks a value, without an effect to sync them on every load.
  const [editedModel, setEditedModel] = useState<string | null>(null);
  const [editedTemperature, setEditedTemperature] = useState<number | null>(null);
  const selectedModel = editedModel ?? activeModel;
  const temperature = editedTemperature ?? activeTemperature;

  const isDirty = selectedModel !== activeModel || temperature !== activeTemperature;
  const isTemperatureValid =
    !Number.isNaN(temperature) && temperature >= MIN_TEMPERATURE && temperature <= MAX_TEMPERATURE;
  const canSave = isDirty && isTemperatureValid && !saving && selectedModel !== "";

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Processing model</h2>
        <span className="hint">Model and temperature used to triage emails</span>
      </div>

      {modelsError && (
        <div className="panel-body">
          <p className="picker-error">{modelsError}</p>
          <button type="button" className="btn" onClick={retryModels}>
            Retry
          </button>
        </div>
      )}

      {!modelsError && modelsLoading && (
        <div className="panel-body">
          <p className="picker-loading">Loading models from Ollama...</p>
        </div>
      )}

      {!modelsError && !modelsLoading && (
        <div className="panel-body">
          <div className="form-row">
            <div className="field">
              <label htmlFor="admin-model-select">Model</label>
              {models.length === 0 ? (
                <p className="picker-error">No models installed in Ollama.</p>
              ) : (
                <select
                  id="admin-model-select"
                  value={selectedModel}
                  disabled={saving}
                  onChange={(e) => setEditedModel(e.target.value)}
                >
                  {models.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="field">
              <label htmlFor="admin-temperature-input">Temperature</label>
              <input
                id="admin-temperature-input"
                type="number"
                min={MIN_TEMPERATURE}
                max={MAX_TEMPERATURE}
                step={0.1}
                value={temperature}
                disabled={saving}
                onChange={(e) => setEditedTemperature(Number(e.target.value))}
              />
            </div>
          </div>

          {!isTemperatureValid && (
            <p className="picker-error">
              Temperature must be between {MIN_TEMPERATURE} and {MAX_TEMPERATURE}.
            </p>
          )}
          {saveError && <p className="picker-error">{saveError}</p>}

          <div style={{ marginTop: 16 }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!canSave}
              onClick={() => applySettings(selectedModel, temperature)}
            >
              {saving ? "Saving..." : "Save"}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
