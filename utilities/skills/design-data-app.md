# Design a Tableau data app (WHAT / why)

Use this **before** calling `local_generate_data_app`. Decide the message and encoding; the generate tool then authors `app.js` / CSS and packages the workbook.

## What this is

A Tableau data app is a custom HTML/JS/CSS viz (worksheet) extension that queries a **published datasource live** via the Extensions API. You render everything yourself — no Marks card, no Show Me.

## Start with the message

1. **Lead with the answer (BLUF).** Headline is a sentence takeaway, not a topic label.
2. **Pyramid:** answer on top → ~3 MECE supporting points → detail on demand.
3. **Shneiderman:** overview → zoom/filter → details on demand.
4. **So what?** If a panel has no action implication, cut it.

## Choose the role

| Role | Question | Density | Interaction |
|------|----------|---------|-------------|
| Strategic | Are we on track? | Low KPIs | Minimal |
| Operational | What is wrong now? | Moderate, actionable | Alerts + light drill |
| Analytical | Why / what if? | High | Rich filters/compare |

Hybrids are fine: strategic strip on top, operational/analytical panels below.

## Encode for the judgment

Perception hierarchy (most → least accurate): position on common scale → length/angle → area → volume → color alone.

- Precise values → **position** (aligned bars / dot plots).
- Trends → **line** on continuous time.
- Ranking → sorted **horizontal bar** (safe default).
- Part-to-whole → bar; pie only for 2–3 rough slices.
- Avoid 3-D, deceptive dual axes, unsorted bars, >7 categorical hues.

## Integrity

- Bars from **zero**.
- No fake dual-axis crossings.
- Surface datasource name + “as of” load time in chrome.
- Don’t imply causation from scatter + trend without caveat.

## Color

- Continuous → sequential/diverging; categorical → ≤5–7 distinct hues.
- Default most marks to grey; **one accent** for the insight mark.
- Never red-vs-green alone for meaning; keep text contrast (WCAG AA).

## Verify (after publish)

Studio gives a browser **preview** with sample aggregates; the true live query runs only inside Tableau after publish. Apply the 5-second test and takeaway test there, then iterate (regenerate → republish).
