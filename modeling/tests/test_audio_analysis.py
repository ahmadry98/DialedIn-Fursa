import json
import math
import sys
import unittest
import wave
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import audio_analysis


def write_synthetic_wav(path: Path, sample_rate=16000):
    duration = 12.0
    samples = np.zeros(int(duration * sample_rate), dtype=np.float32)
    timeline = np.arange(samples.size) / sample_rate
    quiet = 0.01 * np.sin(2 * math.pi * 100 * timeline)
    pump = 0.35 * np.sin(2 * math.pi * 120 * timeline)
    samples += quiet.astype(np.float32)
    active = (timeline >= 2.0) & (timeline <= 10.0)
    samples[active] += pump[active].astype(np.float32)
    pcm = np.clip(samples, -1, 1)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())


class AudioAnalysisTest(unittest.TestCase):
    def test_compute_rms_envelope_returns_energy_timestamps(self):
        samples = np.ones(1600, dtype=np.float32) * 0.5
        timestamps, energies = audio_analysis.compute_rms_envelope(
            samples,
            sample_rate=1600,
            window_seconds=0.5,
            hop_seconds=0.5,
        )
        self.assertEqual(len(timestamps), 2)
        self.assertTrue(np.all(energies > 0.49))

    def test_detect_machine_window_finds_sustained_high_energy_region(self):
        timestamps = np.array([0, 1, 2, 3, 4, 5, 6, 7], dtype=np.float32)
        energies = np.array([0.01, 0.01, 0.5, 0.55, 0.52, 0.5, 0.01, 0.01], dtype=np.float32)
        start, stop, start_conf, stop_conf, requires_confirmation, reason, warnings = audio_analysis.detect_machine_window(
            timestamps,
            energies,
            hop_seconds=1.0,
            min_duration_seconds=2.0,
        )
        self.assertEqual(start, 2.0)
        self.assertEqual(stop, 5.0)
        self.assertGreater(start_conf, 0.4)
        self.assertEqual(stop_conf, start_conf)
        self.assertFalse(requires_confirmation)
        self.assertIsNone(reason)
        self.assertIsInstance(warnings, list)

    def test_detect_machine_window_prefers_plausible_shot_over_short_spike(self):
        timestamps = np.arange(0, 50, dtype=np.float32)
        energies = np.ones_like(timestamps, dtype=np.float32) * 0.01
        energies[10:39] = 0.12
        energies[24:26] = 0.9

        start, stop, start_conf, stop_conf, requires_confirmation, reason, warnings = audio_analysis.detect_machine_window(
            timestamps,
            energies,
            hop_seconds=1.0,
            min_duration_seconds=8.0,
        )

        self.assertLess(start, 15.0)
        self.assertGreater(stop, 35.0)
        self.assertGreater(stop - start, 20.0)
        self.assertGreater(start_conf, 0.5)
        self.assertEqual(stop_conf, start_conf)
        self.assertFalse(requires_confirmation)

    def test_detect_machine_window_ignores_prep_noise_before_sustained_pump(self):
        timestamps = np.arange(0, 55, dtype=np.float32)
        energies = np.ones_like(timestamps, dtype=np.float32) * 0.02
        energies[2:5] = 0.18
        energies[7:46] = 0.52

        start, stop, start_conf, stop_conf, requires_confirmation, reason, warnings = audio_analysis.detect_machine_window(
            timestamps,
            energies,
            hop_seconds=1.0,
            min_duration_seconds=8.0,
        )

        self.assertGreaterEqual(start, 7.0)
        self.assertAlmostEqual(stop, 45.0, delta=1.0)
        self.assertGreater(start_conf, 0.5)
        self.assertEqual(stop_conf, start_conf)
        self.assertFalse(requires_confirmation)
        self.assertIn(
            "Ignored likely prep noise before sustained pump sound.",
            warnings,
        )

    def test_detect_machine_window_requires_confirmation_when_confidence_is_low(self):
        timestamps = np.arange(0, 20, dtype=np.float32)
        energies = np.ones_like(timestamps, dtype=np.float32) * 0.50
        energies[2:14] = 0.56

        (
            start,
            stop,
            start_conf,
            stop_conf,
            requires_confirmation,
            reason,
            warnings,
        ) = audio_analysis.detect_machine_window(
            timestamps,
            energies,
            hop_seconds=1.0,
            min_duration_seconds=8.0,
        )

        self.assertIsNotNone(start)
        self.assertIsNotNone(stop)
        self.assertLess(start_conf, 0.35)
        self.assertEqual(stop_conf, start_conf)
        self.assertTrue(requires_confirmation)
        self.assertIsNotNone(reason)
        self.assertIn("Audio confidence is low; ask the user to confirm timing.", warnings)

    def test_analyze_wav_returns_total_shot_time(self):
        with TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "shot_001.wav"
            write_synthetic_wav(wav_path)
            result = audio_analysis.analyze_wav(wav_path)

        self.assertIsNotNone(result.machine_start_time)
        self.assertIsNotNone(result.machine_stop_time)
        self.assertAlmostEqual(result.machine_start_time, 2.0, delta=0.5)
        self.assertAlmostEqual(result.machine_stop_time, 10.0, delta=0.5)
        self.assertAlmostEqual(result.total_shot_seconds, 8.0, delta=0.75)
        self.assertEqual(result.audio_method, "heuristic_energy")
        self.assertFalse(result.requires_manual_confirmation)
        self.assertIsNone(result.confirmation_reason)

    def test_cli_json_shape_from_wav(self):
        with TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "shot_001.wav"
            write_synthetic_wav(wav_path)
            result = audio_analysis.analyze_media(wav_path)
            payload = json.loads(json.dumps(result.__dict__))

        self.assertIn("machine_start_time", payload)
        self.assertIn("machine_stop_time", payload)
        self.assertIn("total_shot_seconds", payload)
        self.assertIn("requires_manual_confirmation", payload)
        self.assertIn("confirmation_reason", payload)


if __name__ == "__main__":
    unittest.main()
