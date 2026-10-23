"""Ansicht-Anfragen: was im iframe angezeigt werden soll.

Eine Anfrage ist entweder
  TemplateView - ein Template aus templates/<template>.html.j2 plus Daten (backend/rendering.py), oder
  HtmlView     - eigenes HTML, das unverändert angezeigt wird.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Union


@dataclass(frozen=True)
class TemplateView:
    template: str                                    # Name ohne Endung, z. B. "default"
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HtmlView:
    html: str


View = Union[TemplateView, HtmlView]

START_VIEW = TemplateView("default", {
    "title": "Personal Digital Agent",
    "text": "Frag den Assistenten unten nach Daten – sie werden hier angezeigt.",
})
