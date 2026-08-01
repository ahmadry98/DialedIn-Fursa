import type { TimingResult } from "../lib/api";

type TimingCorrectionProps = {
  timing: TimingResult;
  manualStart: string;
  manualStop: string;
  onManualStartChange: (value: string) => void;
  onManualStopChange: (value: string) => void;
  onApply: () => void;
};

export function TimingCorrection({
  timing,
  manualStart,
  manualStop,
  onManualStartChange,
  onManualStopChange,
  onApply,
}: TimingCorrectionProps) {
  const isManual = timing.audio_method === "manual_total_time";
  const startConfidence = timing.start_confidence ?? 1;
  const stopConfidence = timing.stop_confidence ?? 1;
  const showWarning =
    !isManual &&
    (timing.requires_manual_confirmation ||
      Boolean(timing.warnings?.length) ||
      startConfidence < 0.35 ||
      stopConfidence < 0.35);

  return (
    <section className="panel timing-panel" aria-label="Timing correction">
      <div className="panel-heading">
        <div>
          <h2>Timing</h2>
          <p>{isManual ? "user-entered" : timing.audio_method ?? "audio"}</p>
        </div>
        <span className={showWarning ? "status warning" : "status ok"}>
          {isManual ? "Manual" : showWarning ? "Confirm" : "Accepted"}
        </span>
      </div>

      <div className="timing-grid">
        <Metric label="Start" value={isManual ? "manual" : formatTime(timing.machine_start_time)} />
        <Metric label="Stop" value={isManual ? "manual" : formatTime(timing.machine_stop_time)} />
        <Metric label="Total" value={formatTime(timing.total_shot_seconds)} />
        <Metric label="Confidence" value={isManual ? "100%" : formatPercent(Math.min(startConfidence, stopConfidence))} />
      </div>

      {showWarning ? (
        <div className="timing-warning" role="alert">
          <strong>Confirm timing before changing grind.</strong>
          <span>{timing.confirmation_reason || "Audio was noisy or unclear, so the detected start/stop may be wrong."}</span>
        </div>
      ) : null}

      {showWarning ? (
        <div className="correction-row">
          <label>
            Start
            <input
              inputMode="decimal"
              value={manualStart}
              onChange={(event) => onManualStartChange(event.target.value)}
              placeholder="0.00"
            />
          </label>
          <label>
            Stop
            <input
              inputMode="decimal"
              value={manualStop}
              onChange={(event) => onManualStopChange(event.target.value)}
              placeholder="0.00"
            />
          </label>
          <button type="button" className="secondary-button" onClick={onApply}>
            Apply
          </button>
        </div>
      ) : null}

      {timing.warnings?.length ? (
        <ul className="warning-list">
          {timing.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatTime(value: number | null | undefined) {
  return typeof value === "number" ? `${value.toFixed(2)}s` : "--";
}

function formatPercent(value: number | null | undefined) {
  return typeof value === "number" ? `${Math.round(value * 100)}%` : "--";
}
