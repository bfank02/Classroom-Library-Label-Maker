"""Tests for Google Books API key configuration and startup validation."""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.config import (
    GoogleBooksAuthConfig,
    google_books_authentication_message,
    load_application_settings,
    load_google_books_auth_config,
    log_google_books_authentication_status,
)
from classroom_library_label_maker.constants import GOOGLE_BOOKS_API_KEY_ENV
from classroom_library_label_maker.models import GoogleBooksAuthStatus
from classroom_library_label_maker.services.book_enrichment_service import (
    create_default_enrichment_service,
)
from classroom_library_label_maker.services.lookups.google_books import (
    DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS,
    DEFAULT_AUTHENTICATED_MIN_REQUEST_INTERVAL_SECONDS,
    GoogleBooksEnrichmentProvider,
)


def _project_tree(tmp_path: Path) -> Path:
    (tmp_path / "VERSION").write_text("0.1.0\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    for relative in (
        "assets/templates",
        "output/barcodes",
        "logs",
        "temp",
    ):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    return tmp_path


def test_missing_env_disables_authentication_anonymous() -> None:
    auth = load_google_books_auth_config(environ={})
    assert auth.api_key is None
    assert auth.status is GoogleBooksAuthStatus.DISABLED_ANONYMOUS
    assert auth.is_enabled is False


def test_empty_env_value_is_invalid_configuration() -> None:
    auth = load_google_books_auth_config(environ={GOOGLE_BOOKS_API_KEY_ENV: "  "})
    assert auth.api_key is None
    assert auth.status is GoogleBooksAuthStatus.DISABLED_INVALID
    assert auth.is_enabled is False


def test_nonempty_env_enables_authentication() -> None:
    auth = load_google_books_auth_config(
        environ={GOOGLE_BOOKS_API_KEY_ENV: " test-key-123 "}
    )
    assert auth.api_key == "test-key-123"
    assert auth.status is GoogleBooksAuthStatus.ENABLED
    assert auth.is_enabled is True


def test_startup_messages_are_exact() -> None:
    assert (
        google_books_authentication_message(GoogleBooksAuthStatus.ENABLED)
        == "Google Books authentication: Enabled"
    )
    assert (
        google_books_authentication_message(GoogleBooksAuthStatus.DISABLED_ANONYMOUS)
        == "Google Books authentication: Disabled (anonymous mode)"
    )
    assert (
        google_books_authentication_message(GoogleBooksAuthStatus.DISABLED_INVALID)
        == "Google Books authentication: Disabled (invalid API key configuration)"
    )


def test_startup_logging_never_includes_api_key() -> None:
    records: list[str] = []

    class _Capture:
        def info(self, fmt: str, *args: object) -> None:
            records.append(fmt % args if args else fmt)

    log_google_books_authentication_status(
        GoogleBooksAuthStatus.ENABLED,
        logger=_Capture(),
    )
    assert records == ["Google Books authentication: Enabled"]
    assert all("test-key" not in message for message in records)


def test_load_application_settings_injects_auth(tmp_path: Path) -> None:
    root = _project_tree(tmp_path)
    settings = load_application_settings(
        project_root=root,
        environ={GOOGLE_BOOKS_API_KEY_ENV: "settings-key"},
    )
    assert settings.google_books_api_key == "settings-key"
    assert settings.google_books_auth_status is GoogleBooksAuthStatus.ENABLED
    assert settings.google_books_authenticated is True
    assert "settings-key" not in repr(settings)


def test_load_application_settings_anonymous_when_unset(tmp_path: Path) -> None:
    root = _project_tree(tmp_path)
    settings = load_application_settings(project_root=root, environ={})
    assert settings.google_books_api_key is None
    assert settings.google_books_auth_status is GoogleBooksAuthStatus.DISABLED_ANONYMOUS
    assert settings.google_books_authenticated is False


def test_create_default_enrichment_service_injects_api_key() -> None:
    service = create_default_enrichment_service(api_key="injected-key")
    provider = service.provider
    assert isinstance(provider, GoogleBooksEnrichmentProvider)
    assert provider.uses_authentication is True
    assert (
        provider.min_request_interval_seconds
        == DEFAULT_AUTHENTICATED_MIN_REQUEST_INTERVAL_SECONDS
    )


def test_create_default_enrichment_service_anonymous() -> None:
    service = create_default_enrichment_service(api_key=None)
    provider = service.provider
    assert isinstance(provider, GoogleBooksEnrichmentProvider)
    assert provider.uses_authentication is False
    assert (
        provider.min_request_interval_seconds
        == DEFAULT_ANONYMOUS_MIN_REQUEST_INTERVAL_SECONDS
    )


def test_key_file_enables_authentication(tmp_path: Path) -> None:
    key_file = tmp_path / "google_books_api_key.txt"
    key_file.write_text("file-key-abc\n", encoding="utf-8")
    auth = load_google_books_auth_config(environ={}, key_file=key_file)
    assert auth.api_key == "file-key-abc"
    assert auth.status is GoogleBooksAuthStatus.ENABLED


def test_env_takes_precedence_over_key_file(tmp_path: Path) -> None:
    key_file = tmp_path / "google_books_api_key.txt"
    key_file.write_text("file-key\n", encoding="utf-8")
    auth = load_google_books_auth_config(
        environ={GOOGLE_BOOKS_API_KEY_ENV: "env-key"},
        key_file=key_file,
    )
    assert auth.api_key == "env-key"


def test_empty_key_file_is_invalid(tmp_path: Path) -> None:
    key_file = tmp_path / "google_books_api_key.txt"
    key_file.write_text("   \n", encoding="utf-8")
    auth = load_google_books_auth_config(environ={}, key_file=key_file)
    assert auth.status is GoogleBooksAuthStatus.DISABLED_INVALID


def test_auth_config_dataclass_is_immutable() -> None:
    config = GoogleBooksAuthConfig(
        api_key="x",
        status=GoogleBooksAuthStatus.ENABLED,
    )
    assert config.is_enabled is True
