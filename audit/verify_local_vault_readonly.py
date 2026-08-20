from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from modules.local_vault import LocalVault


root = Path(r"C:\Users\DNS\Documents\LocalCometVault")
vault = LocalVault(root)
notes = vault.list_markdown()
print(f"root={vault.identity.canonical_root}")
print(f"root_digest={vault.identity.root_digest}")
print(f"markdown_count={len(notes)}")
for relative_path in notes[:5]:
    note = vault.read_markdown(relative_path)
    print(f"note={note.relative_path} bytes={note.byte_length} sha256={note.sha256}")
