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
    duration = 8.0
    samples = np.zeros(int(duration * sample_rate), dtype=np.float32)
    timeline = np.arange(samples.size) / sample_rate
    quiet = 0.01 * np.sin(2 * math.pi * 100 * timeline)
    pump = 0.35 * np.sin(2 * math.pi * 120 * timeline)
    samples += quiet.astype(np.float32)
    active = (timeline >= 2.0) & (timeline <= 6.0)
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
        start, stop, start_conf, stop_conf, warnings = audio_analysis.detect_machine_window(
            timestamps,
            energies,
            hop_seconds=1.0,
            min_duration_seconds=2.0,
        )
        self.assertEqual(start, 2.0)
        self.assertEqual(stop, 5.0)
        self.assertGreater(start_conf, 0.4)
        self.assertEqual(stop_conf, start_conf)
        self.assertEqual(warnings, [])

    def test_analyze_wav_returns_total_shot_time(self):
        with TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "shot_001.wav"
            write_synthetic_wav(wav_path)
            result = audio_analysis.analyze_wav(wav_path)

        self.assertIsNotNone(result.machine_start_time)
        self.assertIsNotNone(result.machine_stop_time)
        self.assertAlmostEqual(result.machine_start_time, 2.0, delta=0.5)
        self.assertAlmostEqual(result.machine_stop_time, 6.0, delta=0.5)
        self.assertAlmostEqual(result.total_shot_seconds, 4.0, delta=0.75)
        self.assertEqual(result.audio_method, "heuristic_energy")

    def test_cli_json_shape_from_wav(self):
        with TemporaryDirectory() as tmp:
            wav_path = Path(tmp) / "shot_001.wav"
            write_synthetic_wav(wav_path)
            result = audio_analysis.analyze_media(wav_path)
            payload = json.loads(json.dumps(result.__dict__))

        self.assertIn("machine_start_time", payload)
        self.assertIn("machine_stop_time", payload)
        self.assertIn("total_shot_seconds", payload)


if __name__ == "__main__":
    unittest.main()
