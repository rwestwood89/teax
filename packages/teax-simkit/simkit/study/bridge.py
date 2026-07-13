"""`CandidateBridge`: builds the instantiated entry channel model (Shape A).

Isolation-clean at the type level: imports only `pydantic`. The caller (a
study's own `entry_model`) owns the real generated model type; this module
never imports one. Does not type-check — Item 10's `entry_source` is the
type checker.
"""
from __future__ import annotations

from typing import Any, Mapping

from pydantic import BaseModel


class CandidateBridge:
    """Maps a validated candidate's selected fields onto the entry channel's
    typed model. A field the candidate does not select keeps the entry
    model's own modeled default (spec.md#studydefinition).
    """

    def __init__(self, channel_name: str, entry_model: type[BaseModel]) -> None:
        self.channel_name = channel_name
        self.entry_model = entry_model

    def build(self, selected_fields: Mapping[str, Any]) -> dict[str, BaseModel]:
        return {self.channel_name: self.entry_model(**selected_fields)}
