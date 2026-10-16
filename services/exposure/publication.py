"""One atomic P2 publication pointer, with paths confined to the configured data root."""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from services.exposure.aq_provider import AQUnavailableError


class _Publication(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    version: Literal[1]
    generated_at: AwareDatetime
    manifests: tuple[Annotated[str, Field(min_length=1)], ...] = Field(min_length=1, max_length=200)
    fallback: str
    medians: str
    history: str | None = None
    kelurahan: str | None = None
    tiles_available: bool = False


@dataclass(frozen=True)
class Publication:
    generated_at: datetime
    manifests: tuple[Path, ...]
    fallback: Path
    medians: Path
    history: Path | None
    kelurahan: Path | None
    tiles_available: bool

    def settings(self) -> dict[str, str]:
        return {
            "HIRUP_AQ_MANIFESTS": json.dumps([str(path) for path in self.manifests]),
            "HIRUP_AQ_INPUTS": str(self.fallback),
            "HIRUP_CITY_MEDIANS": str(self.medians),
            "HIRUP_AQ_HISTORY": str(self.history) if self.history else "",
            "HIRUP_KELURAHAN_SUMMARIES": str(self.kelurahan) if self.kelurahan else "",
        }

    @classmethod
    def load(cls, data: Path, path: Path) -> "Publication":
        raw = _Publication.model_validate_json(path.read_text(encoding="utf-8"))
        root = data.resolve()

        def resolve(name: str) -> Path:
            relative = Path(name)
            target = (root / relative).resolve()
            if relative.is_absolute() or not target.is_relative_to(root) or not target.is_file():
                raise AQUnavailableError("Publication file is missing or outside the data root")
            return target

        manifests = tuple(resolve(name) for name in raw.manifests)
        if len(set(manifests)) != len(manifests):
            raise AQUnavailableError("Publication repeats a manifest")
        return cls(
            raw.generated_at,
            manifests,
            resolve(raw.fallback),
            resolve(raw.medians),
            resolve(raw.history) if raw.history else None,
            resolve(raw.kelurahan) if raw.kelurahan else None,
            raw.tiles_available,
        )
