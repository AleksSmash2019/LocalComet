import sys
import json
import argparse
import traceback
from pathlib import Path

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from modules.skills.skills_manager import SkillsManager
from modules.skills.skills_contract import SkillError

def main():
    parser = argparse.ArgumentParser(description="LocalComet Skills CLI")
    parser.add_argument("--root", required=True, help="Skills root directory")
    parser.add_argument("action", choices=["list", "metadata", "compile", "install", "enable", "disable", "uninstall"])
    parser.add_argument("--skill-id", help="Skill ID for metadata/compile/enable/disable/uninstall")
    parser.add_argument("--arguments", help="JSON object of bounded workflow parameters")
    parser.add_argument("--archive", help="Path to zip/tar.gz for install")
    
    args = parser.parse_args()
    manager = SkillsManager(args.root)
    
    try:
        manager.ensure_builtins()
        if args.action == "list":
            result = manager.list_skills()
        elif args.action == "metadata":
            if not args.skill_id:
                raise ValueError("--skill-id is required for metadata")
            result = next(item for item in manager.list_skills() if item["id"] == args.skill_id)
        elif args.action == "compile":
            if not args.skill_id:
                raise ValueError("--skill-id is required for compile")
            raw_arguments = json.loads(args.arguments or "{}")
            if not isinstance(raw_arguments, dict):
                raise ValueError("--arguments must be a JSON object")
            result = manager.compile_workflow(args.skill_id, raw_arguments)
        elif args.action == "install":
            if not args.archive:
                raise ValueError("--archive is required for install")
            result = manager.install(args.archive)
        elif args.action == "enable":
            if not args.skill_id:
                raise ValueError("--skill-id is required for enable")
            result = manager.enable(args.skill_id)
        elif args.action == "disable":
            if not args.skill_id:
                raise ValueError("--skill-id is required for disable")
            result = manager.disable(args.skill_id)
        elif args.action == "uninstall":
            if not args.skill_id:
                raise ValueError("--skill-id is required for uninstall")
            result = manager.uninstall(args.skill_id)
        else:
            raise ValueError(f"Unknown action {args.action}")
            
        print(json.dumps({"success": True, "result": result}, ensure_ascii=False))
        sys.exit(0)
    except SkillError as e:
        print(json.dumps({"success": False, "error": {"code": e.code.value, "message": e.message}}, ensure_ascii=False))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"success": False, "error": {"code": "internal_error", "message": str(e)}}, ensure_ascii=False))
        sys.exit(1)

if __name__ == "__main__":
    main()
