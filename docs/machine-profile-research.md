# Machine Profile Research Backlog

This list is a candidate backlog, not verified profile data. Add a machine to
`services/espresso_mcp/machine_profiles.json` only after checking at least one
credible source for its specs.

## Verification Rules

For each machine, collect:

- official product/manual URL when available
- retailer spec URL when official details are incomplete
- aliases/model numbers
- portafilter size
- preinfusion support
- pump/pressure type
- useful grind adjustment notes

Use exact specs only when sourced. If unsure, leave the field `null` or use the
Generic Espresso Machine fallback.


## Target JSON Schema

Keep verified machine specifications separate from app-owned brewing defaults:

```json
{
  "machine_name": "Rancilio Silvia",
  "aliases": ["rancilio silvia", "silvia", "silvia v6"],
  "specs": {
    "portafilter_mm": 58,
    "pump_type": "vibration",
    "pressure_type": "single boiler with vibration pump",
    "has_preinfusion": false
  },
  "brew_defaults": {
    "target_total_shot_seconds": [20, 35],
    "target_visible_flow_seconds": [18, 30],
    "typical_startup_delay_seconds": [2, 6]
  },
  "grind_adjustment_notes": "Use small grind changes and keep dose/yield fixed.",
  "sources": {
    "aliases": ["https://..."],
    "portafilter_mm": ["https://..."],
    "pump_type": ["https://..."],
    "pressure_type": ["https://..."],
    "has_preinfusion": ["https://..."]
  }
}
```

`specs` should be source-backed. `brew_defaults` are DialedIN defaults used by the app and may be adjusted later from user shot history.

## Good Sources

- Official manufacturer product pages and manuals
- Whole Latte Love product/spec pages
- Seattle Coffee Gear product/spec pages
- Clive Coffee product/support pages
- Espresso Parts product pages
- Home-Barista/community pages only for notes, not hard specs

## Candidate Machines

### Entry-Level

1. DeLonghi Stilosa EC260
2. DeLonghi Dedica EC685
3. DeLonghi Dedica Arte EC885
4. Breville Bambino
5. Breville Bambino Plus
6. Gaggia Classic Pro
7. Gaggia Classic E24
8. Lelit Anna PL41TEM
9. Casabrews CM5418
10. Gevi 20 Bar Espresso Machine

### Mid-Range Single Boiler / Thermoblock

11. Rancilio Silvia
12. Rancilio Silvia Pro
13. Lelit Victoria PL91T
14. Lelit Glenda
15. Quick Mill Pippa
16. Profitec GO
17. Stone Espresso Lite
18. Stone Espresso Mine
19. Ascaso Dream PID
20. Ascaso Steel UNO PID

### Heat Exchanger

21. Lelit Mara X
22. Profitec Pro 400
23. Profitec Pro 500 PID
24. ECM Mechanika VI Slim
25. Rocket Appartamento
26. Rocket Mozzafiato
27. Rocket Giotto
28. Bezzera BZ13
29. Bezzera Magica
30. Quick Mill Anita

### Dual Boiler

31. Breville Dual Boiler BES920
32. Lelit Bianca V3
33. Profitec Pro 300
34. Profitec Drive
35. ECM Synchronika II
36. Rocket R58 Cinquantotto
37. Rocket R Nine One
38. La Spaziale Mini Vivaldi II
39. ACS Minima
40. Bellezza Bellona

### Premium / Lever / Specialty

41. La Marzocco Linea Micra
42. La Marzocco Linea Mini
43. Decent DE1Pro
44. Nurri Leva
45. Londinium R24
46. Odyssey Argos
47. Flair 58+
48. Cafelat Robot
49. ACS Vostok
50. Sanremo YOU

## Suggested Expansion Order

Prioritize machines that already appear in our local dataset or are highly common:

1. Lelit Anna PL41TEM
2. La Marzocco Linea Micra
3. La Spaziale Mini Vivaldi II
4. Breville Dual Boiler BES920
5. Profitec GO
6. Lelit Mara X
7. Lelit Bianca V3
8. Rocket Appartamento
9. ECM Synchronika II
10. Flair 58+
