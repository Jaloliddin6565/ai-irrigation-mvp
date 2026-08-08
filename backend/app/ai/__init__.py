"""AI Soil Moisture Proxy / AI Soil Wetness Index — hybrid physics-guided AI
foundation (Phase 1 / Phase 1.1).

This package is an experimental, PRE-CALIBRATION addition alongside the
existing deterministic FAO-56 water-balance engine (app/domain/water_balance.py).
It does NOT replace it: nothing here is wired into
app/services/analysis.py or any API route yet, and per CLAUDE.md the
deterministic engine remains the safe baseline.

Every model trained from this package must always be described as an
"AI soil-moisture proxy" or "AI soil wetness index" (pre-calibration
model) — trained against a public, model-derived (reanalysis) weak label,
not in-situ sensor ground truth, and never described as measuring actual
soil moisture. See app/ai/metadata.py for the full provenance/limitations
record persisted with every trained artifact.

Model versions produced so far (see app/ai/model.py `KNOWN_FEATURE_SCHEMAS`
for the authoritative list a given code version can load):
  - ai_soil_moisture_proxy_v0.1 — Phase 1. Same-day weather only, absolute
    m3/m3 target. Held-out-location R2 was negative; kept on disk as an
    honest historical record, not recommended for further use.
  - ai_soil_moisture_proxy_v0.2 — Phase 1.1. Adds antecedent/rolling
    weather features; still an absolute m3/m3 target.
  - ai_soil_wetness_index_v0.1 — Phase 1.1. Same feature set as v0.2, but a
    location-relative 0-1 target — see app/ai/features.py
    `wetness_index_from_value` and backend/scripts/train_ai_soil_moisture.py
    for why this formulation was added and how it compared.

`RECOMMENDED_MODEL_VERSION` names whichever of the above this codebase
currently recommends, decided from real held-out-location metrics (see
backend/scripts/train_ai_soil_moisture.py) — still Phase 1/1.1: not wired
into any recommendation logic regardless of this value.

Phase 1.1 real result (2023-2025 data, 11 train / 4 held-out test
locations, grouped CV model selection): ai_soil_moisture_proxy_v0.2
(absolute m3/m3) still scored R2=-0.021 held-out — better than Phase 1's
-0.135 but still not usable. ai_soil_wetness_index_v0.1 (location-relative
0-1 target, same features) scored R2=+0.365, clearly beating the global-
mean (-0.148), ridge (+0.097), and random-forest (+0.211) baselines. Hence
the wetness index, not the absolute proxy, is recommended.
"""

RECOMMENDED_MODEL_VERSION = "ai_soil_wetness_index_v0.1"
