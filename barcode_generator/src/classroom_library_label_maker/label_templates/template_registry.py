"""Registry of available :class:`LabelTemplate` specifications."""

from __future__ import annotations

from classroom_library_label_maker.exceptions import ConfigurationError
from classroom_library_label_maker.label_templates.avery_5160 import AVERY_5160
from classroom_library_label_maker.label_templates.label_template import LabelTemplate


class TemplateRegistry:
    """Register and look up immutable label templates by ``template_id``.

    New vendor templates can be registered without changing
    ``LabelLayoutService`` — the service depends on :class:`LabelTemplate` only.
    """

    def __init__(self) -> None:
        """Create an empty registry."""
        self._templates: dict[str, LabelTemplate] = {}

    def register(self, template: LabelTemplate) -> None:
        """Register ``template`` under its ``template_id``.

        Args:
            template: Immutable label template specification.

        Raises:
            ConfigurationError: When ``template_id`` is empty or already registered.
        """
        template_id = template.template_id.strip()
        if not template_id:
            raise ConfigurationError("Cannot register a template with an empty id")
        if template_id in self._templates:
            raise ConfigurationError(
                f"Label template already registered: {template_id!r}"
            )
        self._templates[template_id] = template

    def get(self, template_id: str) -> LabelTemplate:
        """Return the template for ``template_id``.

        Args:
            template_id: Stable template identifier.

        Returns:
            The registered :class:`LabelTemplate`.

        Raises:
            ConfigurationError: When ``template_id`` is unknown.
        """
        key = template_id.strip()
        try:
            return self._templates[key]
        except KeyError as exc:
            available = ", ".join(sorted(self._templates)) or "none"
            raise ConfigurationError(
                f"Unknown label template id: {template_id!r} (available: {available})"
            ) from exc

    def list_templates(self) -> tuple[LabelTemplate, ...]:
        """Return all registered templates sorted by ``template_id``."""
        return tuple(self._templates[key] for key in sorted(self._templates))

    def __contains__(self, template_id: object) -> bool:
        """Return True when ``template_id`` is registered."""
        if not isinstance(template_id, str):
            return False
        return template_id.strip() in self._templates


def create_default_template_registry() -> TemplateRegistry:
    """Return a registry pre-loaded with built-in templates (Avery 5160)."""
    registry = TemplateRegistry()
    registry.register(AVERY_5160)
    return registry
