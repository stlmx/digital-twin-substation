from __future__ import annotations

import os
from pathlib import Path


class Settings:
    data_dir: Path = Path(os.getenv("SUBTWIN_DATA_DIR", "data")).resolve()
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv("SUBTWIN_CORS_ORIGINS", "*").split(",")
        if origin.strip()
    ]
    default_method: str = os.getenv("SUBTWIN_DEFAULT_METHOD", "vggt-colmap")
    default_iterations: int = int(os.getenv("SUBTWIN_DEFAULT_ITERATIONS", "30000"))
    allow_local_import: bool = os.getenv("SUBTWIN_ALLOW_LOCAL_IMPORT", "0") == "1"
    python_bin: str = os.getenv("SUBTWIN_PYTHON_BIN", "python")
    vggt_repo: Path | None = (
        Path(os.environ["SUBTWIN_VGGT_REPO"]).resolve()
        if os.getenv("SUBTWIN_VGGT_REPO")
        else None
    )
    ns_process_data_bin: str = os.getenv("SUBTWIN_NS_PROCESS_DATA_BIN", "ns-process-data")
    ns_train_bin: str = os.getenv("SUBTWIN_NS_TRAIN_BIN", "ns-train")
    ns_export_bin: str = os.getenv("SUBTWIN_NS_EXPORT_BIN", "ns-export")


settings = Settings()
