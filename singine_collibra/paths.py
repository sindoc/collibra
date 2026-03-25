"""Default paths to collibra repo components."""
import os
from pathlib import Path

# Allow override via env var (same convention as COLLIBRA_EDGE_DIR in singine)
COLLIBRA_DIR: Path = Path(
    os.environ.get(
        "COLLIBRA_DIR",
        str(Path(__file__).resolve().parent.parent),
    )
)
IDGEN_DIR: Path = COLLIBRA_DIR / "id-gen"
EDGE_DIR: Path = COLLIBRA_DIR / "edge"
