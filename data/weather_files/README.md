# Singapore-class weather file (`singapore.csv`)

**Provenance, stated plainly:** this is a **synthetic tropical profile**
authored for the P1 weather-domain acceptance (c07) — daytime means
28.5 °C / 82% RH, stand-in irradiance — **not measured Singapore data**.
The corpus item c07 ("run it under the Singapore weather file") needs a
*resolvable* Singapore-class weather file so the `weather_file` field can be
exercised end-to-end; no measured Singapore weather ships with the CityLearn
datasets here (each dataset carries one generic `weather.csv`).

- Format: CityLearn 16-column weather CSV, identical header to the stock
  dataset file.
- Rows: 8761 (header + 8760) — the full-year window; CityLearn broadcasts the
  weather file against the schema's simulation window (the default one-week
  window needs 169 rows; a 24-row file fails with a broadcast error).
- The 24-row daily profile came from Backend/Simulation Engineer A; it was
  extended mechanically (tiled) to the full-year window by the PM on
  2026-11-12 because the delivered file was 24 rows and could not run.
- **Paper obligation:** if this file appears in a reported result, it is a
  synthetic Singapore-class profile, not measured data. Swap in measured
  Singapore weather (e.g. a TMY3/EPW conversion) when available; nothing in
  the pipeline changes.

The adapter fails loudly when a *named* weather file does not resolve (no
silent substitution of the default).
