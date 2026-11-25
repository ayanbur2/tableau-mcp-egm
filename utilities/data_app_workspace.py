"""Local Tableau data-app workspace helpers.

Official @tableau/mcp-server exposes scaffold-data-app + publish-workbook, but not
Claude's upsert/validate/create-and-publish helpers. This module fills that gap for
the local web app: materialize template → edit files → package .twbx.
"""

from __future__ import annotations

import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any

ROOT_PLACEHOLDER = "Data App Name"
TWB_PLACEHOLDER = "Data App Name.twb"
MANIFEST_PLACEHOLDER = "TODO-MANIFEST-ID"
TODO_APP_NAME = "TODO App Name"
TODO_SHEET_NAME = "TODO Sheet Name"
TODO_VERSION = "TODO-MANIFEST-VERSION"
TODO_AUTHOR = "TODO Author Name"
TODO_SOURCE_BUILD = "TODO-SOURCE-BUILD"
DEFAULT_VERSION = "1.0.0"
DEFAULT_AUTHOR = "Tableau MCP"

TEMPLATE_CANDIDATES = [
    Path.home()
    / "AppData/Local/npm-cache/_npx/4c0f68827af2fec6/node_modules/@tableau/mcp-server/build/templates/data-app-template.zip",
]


def default_workspace_root() -> Path:
    return Path(__file__).resolve().parent.parent / "data_apps"


def find_template_zip() -> Path:
    env_path = (Path(__file__).resolve().parent.parent / ".tableau_mcp_template_zip").read_text(encoding="utf-8").strip() if (Path(__file__).resolve().parent.parent / ".tableau_mcp_template_zip").exists() else ""
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.extend(TEMPLATE_CANDIDATES)
    # Also search recent npx caches
    npx_root = Path.home() / "AppData/Local/npm-cache/_npx"
    if npx_root.exists():
        candidates.extend(npx_root.glob("*/node_modules/@tableau/mcp-server/build/templates/data-app-template.zip"))
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(
        "data-app-template.zip not found. Run the app once with npx @tableau/mcp-server so the template is cached."
    )


def slugify_package_id(datapp_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", datapp_name.lower()).strip("-") or "app"
    return f"com.tableau.mcp.{slug}"


def _xml_escape(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def _json_escape(value: str) -> str:
    return json.dumps(value)[1:-1]


def validate_datapp_name(datapp_name: str) -> str:
    name = (datapp_name or "").strip()
    if not name or len(name) > 100:
        raise ValueError("datappName must be 1–100 characters")
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError("datappName must not contain path separators")
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9 ._-]*[A-Za-z0-9])?", name):
        raise ValueError(
            "datappName may only use letters, digits, spaces, dot, underscore, hyphen; "
            "must start and end with a letter or digit"
        )
    return name


def workspace_dir(root: Path, datapp_name: str) -> Path:
    return root / datapp_name


def _clear_readonly(path: Path) -> None:
    """Windows zip extracts often mark files/dirs ReadOnly; clear before mutate/delete."""
    if not path.exists():
        return
    try:
        if path.is_file() or path.is_symlink():
            path.chmod(path.stat().st_mode | 0o222)
            return
        for p in path.rglob("*"):
            try:
                p.chmod(p.stat().st_mode | 0o222)
            except OSError:
                pass
        path.chmod(path.stat().st_mode | 0o222)
    except OSError:
        pass


def _rmtree(path: Path) -> None:
    if not path.exists():
        return
    _clear_readonly(path)

    def _onerror(func, p, _exc_info):
        try:
            Path(p).chmod(Path(p).stat().st_mode | 0o222)
            func(p)
        except OSError:
            pass

    shutil.rmtree(path, onerror=_onerror)


def content_src_dir(root: Path, datapp_name: str) -> Path:
    package_id = slugify_package_id(datapp_name)
    return workspace_dir(root, datapp_name) / "Packages" / package_id / "content" / "src"


def twb_path(root: Path, datapp_name: str) -> Path:
    return workspace_dir(root, datapp_name) / f"{datapp_name}.twb"


def scaffold_workspace(
    datapp_name: str,
    *,
    workspace_root: Path | None = None,
    datasource_luid: str | None = None,
    wire_columns: list[dict[str, str]] | None = None,
    source_build: str = "Tableau MCP (local)",
) -> dict[str, Any]:
    name = validate_datapp_name(datapp_name)
    root = Path(workspace_root) if workspace_root else default_workspace_root()
    root.mkdir(parents=True, exist_ok=True)
    dest = workspace_dir(root, name)
    if dest.exists():
        _rmtree(dest)

    template = find_template_zip()
    staging = root / f".staging_{slugify_package_id(name).split('.')[-1]}"
    if staging.exists():
        _rmtree(staging)
    staging.mkdir(parents=True)

    with zipfile.ZipFile(template) as zf:
        zf.extractall(staging)
    # Template zip entries are often ReadOnly on Windows.
    _clear_readonly(staging)

    package_id = slugify_package_id(name)
    identity = {
        "packageId": package_id,
        "displayName": name,
        "version": DEFAULT_VERSION,
        "author": DEFAULT_AUTHOR,
    }

    # Apply edits on placeholder paths (before renames), matching MCP postUnzip order.
    edits = {
        f"{ROOT_PLACEHOLDER}/{TWB_PLACEHOLDER}": [
            (TODO_SOURCE_BUILD, _xml_escape(f"{source_build}")),
            (MANIFEST_PLACEHOLDER, package_id),
            (TODO_APP_NAME, _xml_escape(name)),
            (TODO_SHEET_NAME, _xml_escape(name)),
            (TODO_VERSION, DEFAULT_VERSION),
        ],
        f"{ROOT_PLACEHOLDER}/Packages/{MANIFEST_PLACEHOLDER}/extensions/data-app.trex": [
            (MANIFEST_PLACEHOLDER, package_id),
            (TODO_APP_NAME, _xml_escape(name)),
            (TODO_VERSION, DEFAULT_VERSION),
            (TODO_AUTHOR, _xml_escape(DEFAULT_AUTHOR)),
        ],
        f"{ROOT_PLACEHOLDER}/Packages/{MANIFEST_PLACEHOLDER}/manifest.json": [
            (MANIFEST_PLACEHOLDER, package_id),
            (TODO_APP_NAME, _json_escape(name)),
            (TODO_VERSION, DEFAULT_VERSION),
            (TODO_AUTHOR, _json_escape(DEFAULT_AUTHOR)),
        ],
    }

    for rel, replacements in edits.items():
        path = staging / rel
        text = path.read_text(encoding="utf-8")
        for find, replace in replacements:
            text = text.replace(find, replace)
        path.write_text(text, encoding="utf-8")

    # Renames inside staging first (folder rename to final name is copy+delete on Windows
    # to avoid WinError 5 when the destination path was recently deleted/locked).
    inner_renames = [
        (
            staging / ROOT_PLACEHOLDER / "Packages" / MANIFEST_PLACEHOLDER,
            staging / ROOT_PLACEHOLDER / "Packages" / package_id,
        ),
        (
            staging / ROOT_PLACEHOLDER / TWB_PLACEHOLDER,
            staging / ROOT_PLACEHOLDER / f"{name}.twb",
        ),
    ]
    for src, dst in inner_renames:
        dst.parent.mkdir(parents=True, exist_ok=True)
        _clear_readonly(src)
        if dst.exists():
            if dst.is_dir():
                _rmtree(dst)
            else:
                _clear_readonly(dst)
                dst.unlink()
        src.rename(dst)

    staged_root = staging / ROOT_PLACEHOLDER
    if dest.exists():
        _rmtree(dest)
    _clear_readonly(staged_root)
    shutil.copytree(staged_root, dest)
    _rmtree(staging)
    _clear_readonly(dest)

    meta = {
        "datappName": name,
        "packageId": package_id,
        "workspaceDir": str(dest.resolve()),
        "twbPath": str(twb_path(root, name).resolve()),
        "contentSrcDir": str(content_src_dir(root, name).resolve()),
        "datasourceLuid": datasource_luid or "",
        "identity": identity,
    }

    if datasource_luid:
        from utilities.tableau_datasource_wire import wire_published_datasource_into_workspace

        wire_info = wire_published_datasource_into_workspace(
            dest,
            twb_path(root, name),
            datasource_luid,
            columns=wire_columns,
        )
        meta["wiredDatasource"] = wire_info

    (dest / ".data-app-meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if datasource_luid:
        # Extensions API ids are workbook-local; empty BOUND uses the first wired DS.
        # Keep meta.datasourceLuid as the published cloud LUID used for wiring.
        _set_bound_datasource_id(root, name, "")

    return meta


def _set_bound_datasource_id(workspace_root: Path, datapp_name: str, bound_id: str) -> Path:
    """Update BOUND_DATASOURCE_ID in src/app.js without changing meta.datasourceLuid."""
    app_js = content_src_dir(workspace_root, datapp_name) / "app.js"
    if not app_js.exists():
        return app_js
    text = app_js.read_text(encoding="utf-8")
    updated = re.sub(
        r"var BOUND_DATASOURCE_ID = '[^']*';",
        f"var BOUND_DATASOURCE_ID = '{bound_id}';",
        text,
        count=1,
    )
    if updated == text and "BOUND_DATASOURCE_ID" in text:
        updated = text.replace(
            "var BOUND_DATASOURCE_ID = '';",
            f"var BOUND_DATASOURCE_ID = '{bound_id}';",
        )
    app_js.write_text(updated, encoding="utf-8")
    return app_js


def bind_datasource_luid(workspace_root: Path, datapp_name: str, datasource_luid: str) -> str:
    """Stamp Extensions API datasource id into starter app.js and meta."""
    app_js = _set_bound_datasource_id(workspace_root, datapp_name, datasource_luid)

    meta_path = workspace_dir(workspace_root, datapp_name) / ".data-app-meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["boundDatasourceId"] = datasource_luid
        if datasource_luid:
            meta["datasourceLuid"] = datasource_luid
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return str(app_js.resolve())


def upsert_files(workspace_root: Path, datapp_name: str, files: dict[str, str]) -> list[str]:
    """Write/replace files under the extension content root or workspace.

    Paths are relative to the package content folder unless prefixed with `workspace:`.
    Examples:
      - src/app.js
      - src/styles.css
      - workspace:Resources/.agents/NOTES.md
    """
    name = validate_datapp_name(datapp_name)
    ws = workspace_dir(workspace_root, name)
    if not ws.exists():
        raise FileNotFoundError(f"Workspace not found: {ws}. Call scaffold first.")

    package_id = slugify_package_id(name)
    content_root = ws / "Packages" / package_id / "content"
    written: list[str] = []
    for rel, content in files.items():
        rel = rel.replace("\\", "/").lstrip("/")
        if rel.startswith("workspace:"):
            target = ws / rel.split("workspace:", 1)[1]
        else:
            target = content_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        # Prevent escaping workspace
        if ws.resolve() not in target.resolve().parents and target.resolve() != ws.resolve():
            raise ValueError(f"Refusing to write outside workspace: {rel}")
        target.write_text(content, encoding="utf-8")
        written.append(str(target.resolve()))
    return written


def read_file(workspace_root: Path, datapp_name: str, relative_path: str) -> str:
    name = validate_datapp_name(datapp_name)
    ws = workspace_dir(workspace_root, name)
    package_id = slugify_package_id(name)
    content_root = ws / "Packages" / package_id / "content"
    rel = relative_path.replace("\\", "/").lstrip("/")
    target = ws / rel.split("workspace:", 1)[1] if rel.startswith("workspace:") else content_root / rel
    if not target.exists():
        raise FileNotFoundError(str(target))
    return target.read_text(encoding="utf-8")


def list_files(workspace_root: Path, datapp_name: str) -> list[str]:
    name = validate_datapp_name(datapp_name)
    ws = workspace_dir(workspace_root, name)
    if not ws.exists():
        raise FileNotFoundError(str(ws))
    out = []
    for p in ws.rglob("*"):
        if p.is_file():
            out.append(str(p.relative_to(ws)).replace("\\", "/"))
    return sorted(out)


def package_twbx(workspace_root: Path, datapp_name: str) -> Path:
    """Package workspace folder into a .twbx next to the workspace."""
    name = validate_datapp_name(datapp_name)
    ws = workspace_dir(workspace_root, name)
    if not ws.exists():
        raise FileNotFoundError(str(ws))
    twb = twb_path(workspace_root, name)
    if not twb.exists():
        raise FileNotFoundError(f"Missing workbook: {twb}")

    out = workspace_root / f"{name}.twbx"
    if out.exists():
        out.unlink()

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in ws.rglob("*"):
            if not path.is_file():
                continue
            # Skip local meta sidecar from packaged bytes if desired? keep it under Resources only.
            if path.name == ".data-app-meta.json":
                continue
            arcname = path.relative_to(ws).as_posix()
            zf.write(path, arcname)
    return out.resolve()


def write_sales_by_month_app_js(profile: dict | None = None) -> str:
    """Live-query monthly line chart; fields come from the selected datasource profile."""
    profile = profile or {}
    measure = profile.get("measure") or "Sales"
    date_field = profile.get("dateField") or "Order Date"
    plan = {"measure": measure, "dateField": date_field}
    template = r"""(function () {
  'use strict';

  var PLAN = __PLAN__;
  var root = document.getElementById('app');
  // Empty = use first workbook datasource (wired at scaffold/publish time).
  var BOUND_DATASOURCE_ID = '';

  function extractData(result) {
    return result && Array.isArray(result.data) ? result.data : [];
  }

  function getDataSources() {
    var wb = tableau.extensions.workbook;
    if (wb && typeof wb.getAllDataSourcesAsync === 'function') {
      return wb.getAllDataSourcesAsync();
    }
    var wc = tableau.extensions.worksheetContent;
    if (wc && wc.worksheet && typeof wc.worksheet.getDataSourcesAsync === 'function') {
      return wc.worksheet.getDataSourcesAsync();
    }
    return Promise.resolve([]);
  }

  function findDataSource(list) {
    if (!BOUND_DATASOURCE_ID) {
      return (list && list.length) ? list[0] : null;
    }
    var found = null;
    (list || []).forEach(function (ds) {
      if (ds && ds.id === BOUND_DATASOURCE_ID) found = ds;
    });
    if (!found) {
      var ids = (list || []).map(function (ds) { return ds && ds.id; }).filter(Boolean);
      throw new Error(
        'Datasource "' + BOUND_DATASOURCE_ID + '" is not in this workbook. Available: ' +
        (ids.length ? ids.join(', ') : '(none)') +
        '. Open the workbook in Tableau, add Superstore Datasource, then reload.'
      );
    }
    return found;
  }

  function renderError(msg) {
    root.textContent = '';
    var p = document.createElement('p');
    p.className = 'error';
    p.textContent = 'Live query unavailable: ' + msg;
    root.appendChild(p);
  }

  function monthKey(value) {
    if (value == null) return '';
    var d = new Date(value);
    if (!isNaN(d.getTime())) {
      var m = String(d.getUTCMonth() + 1).padStart(2, '0');
      return d.getUTCFullYear() + '-' + m;
    }
    return String(value);
  }

  function renderLineChart(rows) {
    root.textContent = '';
    var title = document.createElement('h1');
    title.textContent = 'Total ' + PLAN.measure + ' by Month';
    root.appendChild(title);

    if (!rows.length) {
      var empty = document.createElement('p');
      empty.textContent = 'No rows returned from live query.';
      root.appendChild(empty);
      return;
    }

    var measureRe = new RegExp(PLAN.measure.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
    var dateRe = new RegExp(PLAN.dateField.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '|month|date', 'i');
    var points = rows.map(function (r) {
      var keys = Object.keys(r);
      var orderKey = keys.find(function (k) { return dateRe.test(k); }) || keys[0];
      var salesKey = keys.find(function (k) { return measureRe.test(k); }) || keys[1];
      return { x: monthKey(r[orderKey]), y: Number(r[salesKey]) || 0 };
    }).sort(function (a, b) { return a.x < b.x ? -1 : 1; });

    var maxY = Math.max.apply(null, points.map(function (p) { return p.y; }).concat([1]));
    var width = Math.max(640, points.length * 18);
    var height = 320;
    var pad = 40;

    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 ' + width + ' ' + height);
    svg.setAttribute('width', '100%');
    svg.setAttribute('height', String(height));

    var path = points.map(function (p, i) {
      var x = pad + (i * (width - pad * 2)) / Math.max(points.length - 1, 1);
      var y = height - pad - (p.y / maxY) * (height - pad * 2);
      return (i === 0 ? 'M' : 'L') + x + ' ' + y;
    }).join(' ');

    var line = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    line.setAttribute('d', path);
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', '#1f77b4');
    line.setAttribute('stroke-width', '2');
    svg.appendChild(line);
    root.appendChild(svg);

    var note = document.createElement('p');
    note.textContent = points.length + ' months from live query (' + PLAN.measure + ').';
    root.appendChild(note);
  }

  // Paint shell first (extension handshake can reload the page).
  root.textContent = '';
  var loading = document.createElement('p');
  loading.textContent = 'Loading ' + PLAN.measure + ' by month…';
  root.appendChild(loading);

  tableau.extensions.initializeAsync().then(function () {
    return getDataSources();
  }).then(function (list) {
    var ds = findDataSource(list);
    if (!ds) throw new Error('No datasource is available on this workbook.');
    var query = {
      fields: [
        { fieldCaption: PLAN.dateField, function: 'TRUNC_MONTH' },
        { fieldCaption: PLAN.measure, function: 'SUM' }
      ]
    };
    return ds.queryAsync(query);
  }).then(function (result) {
    renderLineChart(extractData(result));
  }).catch(function (err) {
    var msg = (err && err.message) ? err.message : String(err);
    if (err && err.errorCode) msg = err.errorCode + ': ' + msg;
    renderError(msg);
  });
})();
"""
    return template.replace("__PLAN__", json.dumps(plan))
