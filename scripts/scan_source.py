"""Run detect-secrets serially on source candidates, without printing secret values."""
import subprocess
from pathlib import Path

from detect_secrets import SecretsCollection
from detect_secrets.settings import default_settings


def validate_candidate(root: Path, relative: str) -> Path:
    path = root / relative
    lower = path.name.lower()
    if lower.startswith(".env") or path.suffix.lower() in {".pem", ".key", ".db", ".sqlite", ".sqlite3"}:
        raise ValueError("Private file found in source inventory; review locally")
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Source candidate escapes workspace or is a symbolic link")
    return path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    inventory = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True, check=True,
    )
    candidates = sorted(set(inventory.stdout.decode("utf-8").split("\0")) - {""})
    # Validate the entire inventory before allowing any content reads.
    paths = [validate_candidate(root, candidate) for candidate in candidates]
    scanned = 0
    with default_settings():
        findings = SecretsCollection(root=str(root))
        for path in paths:
            if not path.is_file():  # tracked deletions are not current source
                continue
            # Propagate permission errors rather than letting the detector silently skip a file.
            with path.open("rb") as stream:
                stream.read(1)
            findings.scan_file(path.relative_to(root).as_posix())
            scanned += 1
        if findings.files:
            print(f"FAIL: potential secrets in {len(findings.files)} source files; values withheld.")
            for filename in sorted(findings.files):
                print(f"Review locally: {filename}")
            return 1
    print(f"PASS: secret scan of {scanned} source files; no findings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
