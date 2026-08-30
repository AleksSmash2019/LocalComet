from __future__ import annotations
import json
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
report_dir = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(repo))
from tools.run_isolated_hidden_desktop_cu import cleanup_owned_process_tree  # noqa: E402
from tools import owned_run_cleanup  # noqa: E402

manifest_path = report_dir / owned_run_cleanup.MANIFEST_NAME
manifest = owned_run_cleanup.load_manifest(manifest_path)
owned_pids = [int(pid) for pid in manifest.get("owned_pids", []) if int(pid) > 0]
result = cleanup_owned_process_tree(owned_pids)
plan = owned_run_cleanup.plan_cleanup(
    manifest,
    mode=owned_run_cleanup.MODE_OWNED_CURRENT_RUN,
)
payload = {"owned_pids": owned_pids, "cleanup": result, "post_cleanup_plan": plan}
print(json.dumps({"manifest": str(manifest_path), **payload}, ensure_ascii=False))
(report_dir / "interrupted_owner_cleanup.json").write_text(
    json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
