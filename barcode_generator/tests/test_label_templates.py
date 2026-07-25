"""Tests for label template specifications and registry."""

from __future__ import annotations

import pytest

from classroom_library_label_maker.exceptions import ConfigurationError
from classroom_library_label_maker.label_templates import (
    AVERY_5160,
    AVERY_5160_TEMPLATE_ID,
    Avery5160,
    LabelTemplate,
    LabelTemplateSpec,
    PageOrientation,
    PageSize,
    TemplateRegistry,
    create_default_template_registry,
)
from classroom_library_label_maker.models import ApplicationSettings


def test_avery_5160_official_values() -> None:
    """Avery 5160 should match the published Letter / 3x10 layout."""
    template = AVERY_5160
    assert template.template_id == "avery-5160"
    assert template.vendor == "Avery"
    assert template.product_number == "5160"
    assert template.page_size is PageSize.LETTER
    assert template.orientation is PageOrientation.PORTRAIT
    assert template.page_width == 8.5
    assert template.page_height == 11.0
    assert template.rows == 10
    assert template.columns == 3
    assert template.label_width == 2.625
    assert template.label_height == 1.0
    assert template.top_margin == 0.5
    assert template.left_margin == 0.1875
    assert template.horizontal_gap == 0.125
    assert template.vertical_gap == 0.0


def test_avery_5160_derived_properties() -> None:
    """Derived properties should be computed from layout fields."""
    assert AVERY_5160.labels_per_page == 30
    assert AVERY_5160.printable_width == pytest.approx(8.125)
    assert AVERY_5160.printable_height == pytest.approx(10.0)
    assert Avery5160.as_template() is AVERY_5160
    assert Avery5160.template_id == AVERY_5160_TEMPLATE_ID


def test_template_immutability() -> None:
    """Frozen templates must reject attribute assignment."""
    with pytest.raises(AttributeError):
        AVERY_5160.rows = 99  # type: ignore[misc]


def test_registry_registration_and_lookup() -> None:
    """Registry should register and retrieve templates by id."""
    registry = TemplateRegistry()
    registry.register(AVERY_5160)
    assert "avery-5160" in registry
    assert registry.get("avery-5160") is AVERY_5160
    assert registry.list_templates() == (AVERY_5160,)


def test_registry_unknown_template_raises_configuration_error() -> None:
    """Unknown template ids must raise ConfigurationError (never None)."""
    registry = create_default_template_registry()
    with pytest.raises(ConfigurationError, match="Unknown label template"):
        registry.get("does-not-exist")


def test_default_registry_includes_avery_5160() -> None:
    """Default registry should ship with Avery 5160 only."""
    registry = create_default_template_registry()
    assert [t.template_id for t in registry.list_templates()] == ["avery-5160"]


def test_duplicate_registration_rejected() -> None:
    """Registering the same template id twice should fail."""
    registry = create_default_template_registry()
    with pytest.raises(ConfigurationError, match="already registered"):
        registry.register(AVERY_5160)


def test_label_template_id_settings_default(
    app_settings: ApplicationSettings,
) -> None:
    """ApplicationSettings should default label_template_id to avery-5160."""
    assert app_settings.label_template_id == "avery-5160"
    template = create_default_template_registry().get(app_settings.label_template_id)
    assert template.template_id == "avery-5160"


def test_public_api_exports() -> None:
    """Package exports should expose the intended public interfaces."""
    import classroom_library_label_maker.label_templates as package

    assert set(package.__all__) == {
        "AVERY_5160",
        "AVERY_5160_TEMPLATE_ID",
        "Avery5160",
        "LabelTemplate",
        "LabelTemplateSpec",
        "PageOrientation",
        "PageSize",
        "TemplateRegistry",
        "create_default_template_registry",
    }
    assert isinstance(AVERY_5160, LabelTemplateSpec)
    # Structural protocol check
    template: LabelTemplate = AVERY_5160
    assert template.labels_per_page == 30
