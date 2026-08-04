import type { AnalyzeShotResponse } from "../lib/api";
import { TimingCorrection } from "./timing-correction";

type ShotResultProps = {
  result: AnalyzeShotResponse;
  manualStart: string;
  manualStop: string;
  onManualStartChange: (value: string) => void;
  onManualStopChange: (value: string) => void;
  onApplyTiming: () => void;
};

export function ShotResult({
  result,
  manualStart,
  manualStop,
  onManualStartChange,
  onManualStopChange,
  onApplyTiming,
}: ShotResultProps) {
  const profileName = String(result.machine_profile.machine_name ?? "Generic Espresso Machine");

  return (
    <div className="result-layout">
      <TimingCorrection
        timing={result.timing}
        manualStart={manualStart}
        manualStop={manualStop}
        onManualStartChange={onManualStartChange}
        onManualStopChange={onManualStopChange}
        onApply={onApplyTiming}
      />

      <section className="panel recommendation-panel" aria-label="Recommendation">
        <div className="panel-heading">
          <div>
            <h2>Recommendation</h2>
            <p>{profileName}</p>
          </div>
          <span className="status ok">{result.recommendation.confidence}</span>
        </div>

        <div className="recommendation-action">{humanize(result.recommendation.recommendation)}</div>
        <p className="recommendation-adjustment">{result.recommendation.adjustment}</p>
        {result.recommendation.exact_grind_setting?.setting_label ? (
          <div className="exact-setting">
            <span>Next setting</span>
            <strong>{result.recommendation.exact_grind_setting.setting_label}</strong>
          </div>
        ) : null}
        <p className="reason">{result.recommendation.reason}</p>

        {result.recommendation.calculation_explanation?.length ? (
          <div className="explanation-block" aria-label="Calculation explanation">
            <h3>Why this setting</h3>
            <ul>
              {result.recommendation.calculation_explanation.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}

        {result.recommendation.confidence_reasons?.length ? (
          <div className="explanation-block muted-block" aria-label="Recommendation confidence details">
            <h3>Confidence</h3>
            <ul>
              {result.recommendation.confidence_reasons.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        ) : null}

        <div className="detail-row">
          <span>Target</span>
          <strong>
            {result.recommendation.target_range_seconds[0]}-{result.recommendation.target_range_seconds[1]}s
          </strong>
        </div>

      </section>

      {result.profile_candidates?.length ? (
        <section className="panel candidate-panel" aria-label="Profile candidates">
          <div className="panel-heading">
            <div>
              <h2>Profile queue</h2>
              <p>Generic fallback used</p>
            </div>
          </div>
          <div className="tag-group">
            {result.profile_candidates.map((candidate) => (
              <span className="tag warning-tag" key={`${candidate.type}-${candidate.name_entered}`}>
                {candidate.type}: {candidate.name_entered}
              </span>
            ))}
          </div>
        </section>
      ) : null}

      {result.missing_fields.length ? (
        <section className="panel missing-panel" aria-label="Missing fields">
          <div className="panel-heading">
            <div>
              <h2>Missing</h2>
              <p>Improve the next recommendation</p>
            </div>
          </div>
          <div className="tag-group">
            {result.missing_fields.map((field) => (
              <span className="tag muted" key={field}>{field}</span>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}

function humanize(value: string) {
  return value.replaceAll("_", " ");
}
