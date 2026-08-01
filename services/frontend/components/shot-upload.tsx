"use client";

import { FormEvent, useState } from "react";
import { analyzeShot, AnalyzeShotResponse, ShotFormValues } from "../lib/api";
import { ShotResult } from "./shot-result";
import {
  getGrinderProfile,
  grinderOptions,
  machineHasKnownBuiltInGrinder,
  machineSupportsBuiltInGrinder,
  grindSettingHint,
  grindSettingOptions,
  grindSettingStep,
  machineOptions,
  validateGrindSetting,
} from "../lib/gear-options";

type FormState = {
  user_id: string;
  video_s3_key: string;
  machine: string;
  grinder: string;
  uses_built_in_grinder: boolean;
  dose_g: string;
  yield_g: string;
  grind_setting: string;
  roast_level: string;
  taste: string;
};

const initialForm: FormState = {
  user_id: "demo-user",
  video_s3_key: "",
  machine: "",
  grinder: "",
  uses_built_in_grinder: false,
  dose_g: "18",
  yield_g: "",
  grind_setting: "",
  roast_level: "",
  taste: "",
};

export function ShotUpload() {
  const [form, setForm] = useState<FormState>(initialForm);
  const [selectedFile, setSelectedFile] = useState("");
  const [result, setResult] = useState<AnalyzeShotResponse | null>(null);
  const [manualStart, setManualStart] = useState("");
  const [manualStop, setManualStop] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");

  const builtInGrinderAllowed = machineSupportsBuiltInGrinder(form.machine);
  const effectiveUsesBuiltInGrinder = form.uses_built_in_grinder && builtInGrinderAllowed;
  const effectiveGrinderName = effectiveUsesBuiltInGrinder ? "" : form.grinder;
  const selectedGrinderProfile = getGrinderProfile(effectiveGrinderName);
  const selectedGrindSettingOptions = grindSettingOptions(selectedGrinderProfile);
  const selectedGrindSettingStep = grindSettingStep(selectedGrinderProfile);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const payload = buildPayload({ ...form, uses_built_in_grinder: effectiveUsesBuiltInGrinder });

    if (payload.video_s3_key?.endsWith("/")) {
      setError("Choose a video file or enter the full video path, for example data/raw-videos/shot_007.mp4.");
      return;
    }

    const grindSettingError = validateGrindSetting(form.grind_setting, selectedGrinderProfile);
    if (grindSettingError) {
      setError(grindSettingError);
      return;
    }

    await runAnalysis(payload);
  }

  async function handleApplyTiming() {
    const start = parseOptionalNumber(manualStart);
    const stop = parseOptionalNumber(manualStop);

    if (start === undefined || stop === undefined || stop <= start) {
      setError("Enter a valid start and stop time.");
      return;
    }

    await runAnalysis({
      ...buildPayload({ ...form, uses_built_in_grinder: effectiveUsesBuiltInGrinder }),
      video_s3_key: undefined,
      total_shot_seconds: round(stop - start),
      timing_confidence: 1,
      requires_manual_confirmation: false,
    });
  }

  async function runAnalysis(payload: ShotFormValues) {
    setIsLoading(true);
    setError("");

    try {
      const response = await analyzeShot(payload);
      setResult(response);
      setManualStart(formatInputTime(response.timing.machine_start_time));
      setManualStop(formatInputTime(response.timing.machine_stop_time));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Unable to analyze shot.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="workspace">
      <form className="form-panel" onSubmit={handleSubmit}>
        <div className="form-grid">
          <label className="field full file-control">
            Video
            <input
              type="file"
              accept="video/mp4,video/quicktime,video/*"
              onChange={(event) => {
                const fileName = event.target.files?.[0]?.name ?? "";
                setSelectedFile(fileName);
                if (fileName) {
                  updateField("video_s3_key", "data/raw-videos/" + fileName);
                }
              }}
            />
            <span className="file-name">{selectedFile || "No local file selected"}</span>
          </label>

          <label className="field full">
            Video key
            <input
              value={form.video_s3_key}
              onChange={(event) => updateField("video_s3_key", event.target.value)}
              placeholder="data/raw-videos/shot_014.mp4 or S3 key"
            />
          </label>

          <label className="field">
            Machine
            <input
              list="machine-options"
              value={form.machine}
              onChange={(event) => updateField("machine", event.target.value)}
              placeholder="Choose or type machine"
            />
          </label>

          <div className="field grinder-field">
            <div className="field-row">
              <span>Grinder</span>
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={effectiveUsesBuiltInGrinder}
                  disabled={!builtInGrinderAllowed}
                  title={builtInGrinderAllowed ? "Use the machine built-in grinder" : "This machine profile does not have a built-in grinder"}
                  onChange={(event) => toggleBuiltInGrinder(event.target.checked)}
                />
                Built-in
              </label>
            </div>
            <input
              list="grinder-options"
              value={effectiveUsesBuiltInGrinder ? "Built-in grinder" : form.grinder}
              onChange={(event) => updateField("grinder", event.target.value)}
              placeholder="Choose or type grinder"
              disabled={effectiveUsesBuiltInGrinder}
            />
          </div>

          <label className="field">
            Dose g
            <input
              inputMode="decimal"
              value={form.dose_g}
              onChange={(event) => updateField("dose_g", event.target.value)}
              placeholder="18"
            />
          </label>

          <label className="field">
            Yield g optional
            <input
              inputMode="decimal"
              value={form.yield_g}
              onChange={(event) => updateField("yield_g", event.target.value)}
              placeholder="36"
            />
          </label>

          <div className="field-pair full">
            <label className="field">
              Grind setting
              <input
                type="number"
                list="grind-setting-options"
                min={selectedGrinderProfile?.min_setting ?? undefined}
                max={selectedGrinderProfile?.max_setting ?? undefined}
                step={selectedGrindSettingStep ?? "any"}
                value={form.grind_setting}
                onChange={(event) => updateField("grind_setting", event.target.value)}
                placeholder={selectedGrinderProfile?.espresso_range?.[0]?.toString() ?? "12"}
              />
              <span className="field-hint">{grindSettingHint(selectedGrinderProfile)}</span>
            </label>

            <label className="field align-input-top">
              Roast level
              <select value={form.roast_level} onChange={(event) => updateField("roast_level", event.target.value)}>
                <option value="">Unknown</option>
                <option value="light">Light</option>
                <option value="medium">Medium</option>
                <option value="dark">Dark</option>
              </select>
            </label>
          </div>

          <label className="field full">
            Taste
            <textarea
              value={form.taste}
              onChange={(event) => updateField("taste", event.target.value)}
              placeholder="sour, bitter, balanced, thin, harsh"
            />
          </label>
        </div>

        <datalist id="machine-options">
          {machineOptions.map((machine) => (
            <option value={machine} key={machine} />
          ))}
        </datalist>
        <datalist id="grinder-options">
          {grinderOptions.map((grinder) => (
            <option value={grinder} key={grinder} />
          ))}
        </datalist>
        <datalist id="grind-setting-options">
          {selectedGrindSettingOptions.map((setting) => (
            <option value={setting} key={setting} />
          ))}
        </datalist>

        <div className="form-actions">
          <span className="muted-text">{form.user_id}</span>
          <button className="primary-button" type="submit" disabled={isLoading}>
            {isLoading ? "Analyzing" : "Analyze"}
          </button>
        </div>

        {error ? <div className="alert">{error}</div> : null}
      </form>

      {result ? (
        <ShotResult
          result={result}
          manualStart={manualStart}
          manualStop={manualStop}
          onManualStartChange={setManualStart}
          onManualStopChange={setManualStop}
          onApplyTiming={handleApplyTiming}
        />
      ) : (
        <section className="panel empty-state" aria-label="No result">
          <p>Run a shot to see timing and grind guidance.</p>
        </section>
      )}
    </div>
  );

  function updateField(field: keyof FormState, value: string) {
    setForm((current) => {
      const next = { ...current, [field]: value };
      if (field === "machine") {
        if (machineHasKnownBuiltInGrinder(value)) {
          next.uses_built_in_grinder = true;
        } else if (!machineSupportsBuiltInGrinder(value)) {
          next.uses_built_in_grinder = false;
        }
      }
      return next;
    });
  }

  function toggleBuiltInGrinder(checked: boolean) {
    setForm((current) => ({
      ...current,
      uses_built_in_grinder: checked,
      grinder: checked ? "" : current.grinder,
    }));
  }
}

function buildPayload(form: FormState): ShotFormValues {
  return {
    user_id: form.user_id,
    video_s3_key: form.video_s3_key,
    machine: form.machine,
    grinder: form.uses_built_in_grinder ? `${form.machine || "Machine"} built-in grinder` : form.grinder,
    uses_built_in_grinder: form.uses_built_in_grinder,
    dose_g: parseOptionalNumber(form.dose_g),
    yield_g: parseOptionalNumber(form.yield_g),
    grind_setting: form.grind_setting,
    roast_level: form.roast_level,
    taste: form.taste,
  };
}

function parseOptionalNumber(value: string) {
  if (!value.trim()) {
    return undefined;
  }

  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function formatInputTime(value: number | null | undefined) {
  return typeof value === "number" ? String(round(value)) : "";
}

function round(value: number) {
  return Math.round(value * 100) / 100;
}
