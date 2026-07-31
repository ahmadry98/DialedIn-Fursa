# Audio Timing Evaluation

All videos: detected 14/14 videos. Average absolute start error: 2.04s. Average absolute stop error: 2.15s. Average absolute total-time error: 2.09s. Within 3s total-time target: 12/14. Low confidence detections: 2/14. Manual confirmation needed: 2/14. Visual fallback recommended: 3/14.
Clean videos only: detected 12/12 videos. Average absolute start error: 1.14s. Average absolute stop error: 1.33s. Average absolute total-time error: 0.86s. Within 3s total-time target: 12/12. Low confidence detections: 1/12. Manual confirmation needed: 1/12. Visual fallback recommended: 1/12.
Noisy/talking videos only: detected 2/2 videos. Average absolute start error: 7.47s. Average absolute stop error: 7.10s. Average absolute total-time error: 9.45s. Within 3s total-time target: 0/2. Low confidence detections: 1/2. Manual confirmation needed: 1/2. Visual fallback recommended: 2/2.

video_id | audio_quality | manual_start | manual_stop | detected_start | detected_stop | start_err | stop_err | total_err | confidence | confirm | visual_fallback | warnings
--- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | ---
shot_001 | clean | 14.00 | 46.00 | 14.02 | 46.03 | +0.02 | +0.03 | +0.01 | 0.68 | no | no | Audio threshold was low; ask the user to confirm timing.
shot_002 | clean | 4.00 | 26.00 | 4.22 | 25.62 | +0.22 | -0.38 | -0.60 | 0.98 | no | no | Audio threshold was low; ask the user to confirm timing.
shot_003 | clean | 1.00 | 19.00 | 1.23 | 18.33 | +0.23 | -0.67 | -0.90 | 0.58 | no | no | Audio threshold was low; ask the user to confirm timing.
shot_004 | clean | 8.00 | 37.00 | 6.82 | 36.33 | -1.18 | -0.67 | +0.51 | 0.26 | yes | yes | Audio threshold was low; ask the user to confirm timing.; Audio confidence is low; ask the user to confirm timing.
shot_005 | clean | 2.00 | 30.00 | 9.52 | 39.22 | +7.52 | +9.22 | +1.70 | 0.55 | no | no | 
shot_006 | talking | 4.00 | 27.00 | 9.12 | 36.53 | +5.12 | +9.53 | +4.41 | 0.61 | no | yes | Audio threshold was low; ask the user to confirm timing.
shot_007 | clean | 7.00 | 39.00 | 6.43 | 36.42 | -0.57 | -2.58 | -2.01 | 0.56 | no | no | Audio threshold was low; ask the user to confirm timing.
shot_008 | talking | 4.00 | 27.00 | 13.82 | 22.33 | +9.82 | -4.67 | -14.49 | 0.16 | yes | yes | Audio threshold was low; ask the user to confirm timing.; Audio confidence is low; ask the user to confirm timing.
shot_009 | clean | 7.60 | 49.00 | 7.43 | 48.33 | -0.17 | -0.67 | -0.50 | 0.98 | no | no | Audio threshold was low; ask the user to confirm timing.
shot_010 | clean | 2.00 | 34.00 | 1.42 | 33.42 | -0.58 | -0.58 | +0.00 | 0.76 | no | no | Audio threshold was low; ask the user to confirm timing.
shot_011 | clean | 6.70 | 35.00 | 6.43 | 35.03 | -0.27 | +0.03 | +0.30 | 0.80 | no | no | Audio threshold was low; ask the user to confirm timing.
shot_012 | clean | 4.00 | 21.00 | 2.42 | 21.33 | -1.58 | +0.33 | +1.91 | 0.95 | no | no | Audio threshold was low; ask the user to confirm timing.
shot_013 | clean | 4.00 | 27.00 | 4.22 | 26.33 | +0.22 | -0.67 | -0.89 | 0.98 | no | no | Audio threshold was low; ask the user to confirm timing.
shot_014 | clean | 6.00 | 46.00 | 4.93 | 45.92 | -1.07 | -0.08 | +0.99 | 0.75 | no | no | Ignored likely prep noise before sustained pump sound.
