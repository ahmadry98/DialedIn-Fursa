# Raw Espresso Shot Videos

Place the first controlled espresso shot videos in this folder.

## Recording Rules

- Start recording before pressing the machine button, switch, or lever.
- Stop recording only after coffee flow has clearly ended.
- Keep the camera angle consistent for the first dataset.
- Make sure the machine control area is visible: button, light, screen, switch, or lever.
- Make sure the espresso area is visible: portafilter, cup, and coffee stream.
- Avoid changing camera position during the shot.
- Use short filenames with stable IDs, for example `shot_001.mp4`, `shot_002.mp4`.

## First Dataset Target

Start with 10-20 videos from a controlled angle. The first goal is not variety; the first goal is proving that the model can learn shot states from consistent examples.

## Labeling

For every video added here, add one row to `data/labels/shot_labels.csv`. Timestamps are seconds from the start of the video.
