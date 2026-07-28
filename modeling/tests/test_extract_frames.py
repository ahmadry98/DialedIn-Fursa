import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import extract_frames


class FakeCapture:
    def __init__(self, path):
        self.path = path
        self.position_ms = 0.0
        self.reads = 0
        self.opened = True

    def isOpened(self):
        return self.opened

    def get(self, prop):
        if prop == fake_cv2.CAP_PROP_FPS:
            return 4.0
        if prop == fake_cv2.CAP_PROP_FRAME_COUNT:
            return 8
        return 0

    def set(self, prop, value):
        self.assertable_prop = prop
        self.position_ms = value

    def read(self):
        if self.position_ms > 2000:
            return False, None
        self.reads += 1
        return True, {"position_ms": self.position_ms}

    def release(self):
        self.opened = False


class FakeCv2:
    CAP_PROP_FPS = 5
    CAP_PROP_FRAME_COUNT = 7
    CAP_PROP_POS_MSEC = 0

    def VideoCapture(self, path):
        return FakeCapture(path)

    def imwrite(self, path, frame):
        Path(path).write_text(str(frame))
        return True


fake_cv2 = FakeCv2()


class ExtractFramesTest(unittest.TestCase):
    def test_frame_filename_includes_timestamp(self):
        self.assertEqual(
            extract_frames.frame_filename("shot_001", 2.5),
            "shot_001_t0002.50.jpg",
        )

    def test_prepare_output_dir_refuses_non_empty_directory(self):
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "shot_001"
            output_dir.mkdir()
            (output_dir / "existing.jpg").write_text("old")

            with self.assertRaisesRegex(FileExistsError, "--overwrite"):
                extract_frames.prepare_output_dir(output_dir, overwrite=False)

    def test_extract_frames_writes_timestamped_frames_and_metadata(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            video_path = tmp_path / "shot_001.mp4"
            video_path.write_text("fake video")

            with patch.dict(sys.modules, {"cv2": fake_cv2}):
                result = extract_frames.extract_frames(
                    video_path,
                    output_root=tmp_path / "frames",
                    fps=2,
                )

            output_dir = tmp_path / "frames" / "shot_001"
            self.assertEqual(result.frames_written, 5)
            self.assertTrue((output_dir / "shot_001_t0000.00.jpg").exists())
            self.assertTrue((output_dir / "shot_001_t0000.50.jpg").exists())
            self.assertTrue((output_dir / "shot_001_t0001.00.jpg").exists())
            self.assertTrue((output_dir / "shot_001_t0001.50.jpg").exists())
            self.assertTrue((output_dir / "shot_001_t0002.00.jpg").exists())

            metadata = json.loads((output_dir / "metadata.json").read_text())
            self.assertEqual(metadata["video_id"], "shot_001")
            self.assertEqual(metadata["fps_requested"], 2)
            self.assertEqual(metadata["frames_written"], 5)

    def test_discover_videos_returns_sorted_supported_files(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "shot_002.mp4").write_text("video")
            (tmp_path / "notes.txt").write_text("ignore")
            (tmp_path / "shot_001.mov").write_text("video")

            videos = extract_frames.discover_videos(tmp_path)

            self.assertEqual(
                [video.name for video in videos],
                ["shot_001.mov", "shot_002.mp4"],
            )


if __name__ == "__main__":
    unittest.main()
