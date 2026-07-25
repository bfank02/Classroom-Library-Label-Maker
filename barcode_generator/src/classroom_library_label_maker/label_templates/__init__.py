"""Label template specifications (physical layout only).

Isolates vendor sheet geometry from future layout / rendering engines.
All measurements are inches. Templates are immutable value objects.

Public API
----------
* :class:`LabelTemplate` — protocol for physical sheet specs
* :class:`LabelTemplateSpec` — frozen dataclass implementation
* :class:`PageSize` / :class:`PageOrientation` — page enums
* :class:`TemplateRegistry` / :func:`create_default_template_registry`
* :data:`AVERY_5160` / :class:`Avery5160` — built-in Avery 5160 template
"""

from __future__ import annotations

from classroom_library_label_maker.label_templates.avery_5160 import (
    AVERY_5160,
    AVERY_5160_TEMPLATE_ID,
    Avery5160,
)
from classroom_library_label_maker.label_templates.label_template import (
    LabelTemplate,
    LabelTemplateSpec,
    PageOrientation,
    PageSize,
)
from classroom_library_label_maker.label_templates.template_registry import (
    TemplateRegistry,
    create_default_template_registry,
)

__all__ = [
    "AVERY_5160",
    "AVERY_5160_TEMPLATE_ID",
    "Avery5160",
    "LabelTemplate",
    "LabelTemplateSpec",
    "PageOrientation",
    "PageSize",
    "TemplateRegistry",
    "create_default_template_registry",
]
