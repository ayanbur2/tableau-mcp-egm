# Build a Tableau data app (HOW) — Studio tools

Companion to `design-data-app.md`. This maps Claude’s authoring workflow onto **this Studio’s tools**.

## Live-query model

- Runtime: `tableau.extensions.initializeAsync()` → workbook datasources → `readMetadataAsync` / `queryAsync`.
- Match columns by **field name/caption**, not position.
- Prerequisite: datasource must be **wired into the .twb**. Name-only scaffold leaves empty `<datasources/>` and shows “no data source found.”
- Studio’s `local_generate_data_app` scaffolds **and wires** the Active Datasource (sqlproxy) before packaging — prefer it over bare `scaffold-data-app` / `local_scaffold_data_app`.

## When to build a real app

Author beyond a one-line answer when the user asks to chart / visualize / build a dashboard / data app over a published datasource. Skip for single-value lookups unless they ask for a reusable visual.

## Studio workflow (do this)

1. **Design (WHAT).** Apply `design-data-app.md`: role, takeaway sentence, encodings. Put that into a concrete `brief`.
2. **Identify datasource.** Use Active Datasource LUID from chat (`datasourceLuid=…`). Never invent Superstore. If ambiguous, ask.
3. **Introspect (optional but preferred for complex apps).**
   - `get-datasource-metadata` → field list the app will match by name.
   - `query-datasource` → sanity-check the aggregates the app will chart.
4. **Generate (preferred one-shot).** Call **`local_generate_data_app`** with:
   - `datasource_luid` = Active LUID
   - `brief` = design takeaway + audience + chart intent + color/theme
   - optional `theme` = `red|green|blue`
   - It invents NEW `src/app.js` + `styles.css`, scaffolds, **wires** the DS, writes browser `previewUrl`, packages `.twbx`.
5. **Return the new `previewUrl` (`?v=`).** Studio preview uses sample aggregates for visual review; live Extensions query runs after publish in Tableau.
6. **Never auto-publish.** Ask clearly whether to publish.
7. **On publish yes:**
   - `local_resolve_publish_workbook` (do **not** regenerate)
   - `list-projects` → ask which project → followup chips `Publish to <Name> (projectId=<uuid>)`
   - Only then `publish-workbook` with chosen `projectId`, `overwrite=true`, no personalSpace
8. **Review in Tableau.** Open the returned URL; confirm the viz-extension worksheet (trust prompt once is OK). Iterate: new generate → resolve → republish.

## Manual / advanced path (rare)

Only if the user asks to edit files step-by-step:

1. `local_scaffold_data_app` or MCP `scaffold-data-app` + bind/wire
2. Introspect fields
3. `local_upsert_data_app_files` for `src/app.js` / `src/styles.css`
4. `local_package_data_app`
5. Preview / publish as above

Prefer **`local_generate_data_app`** for normal requests — it is the Studio equivalent of scaffold → wire → author → package.

## Authoring rules inside app.js

- Paint loading/error shell **before** `initializeAsync`.
- Live path: `workbook.getAllDataSourcesAsync()` (or `worksheetContent`) → `ds.queryAsync` + safe DOM (`textContent` / `createElement`).
- **Never** `tableau.extensions.dashboardContent` — this is a viz/worksheet extension; that API is undefined and throws `Cannot read properties of undefined (reading 'dashboard')`.
- **Never** `getSummaryDataAsync` for the data-app path — use `queryAsync`.
- Bake field captions into app.js; do not rely on `window.__THEME__` in Tableau.
- No CDN; SVG/Canvas/DOM only (vendored Extensions JS already in package).
- Preview path: honor `window.__DATA_APP_PREVIEW__` / `__PREVIEW_SAMPLE__` when present.
- Find datasource by name/caption (or first workbook DS when `BOUND_DATASOURCE_ID` is empty after wire).

## Do not

- Call `local_rebuild_data_app` / seed templates unless the user asks for a fixed template.
- Regenerate when the user only asked to publish.
- Assume Samples or any default projectId.
