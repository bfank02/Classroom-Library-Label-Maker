"""Barcode renderer backed by the ``python-barcode`` library.

Third-party types stay inside this module. Callers only see ``pathlib.Path``
and application enums from the :class:`BarcodeRenderer` contract.
"""

from __future__ import annotations

from pathlib import Path

from classroom_library_label_maker.constants import (
    DEFAULT_BARCODE_DPI,
    DEFAULT_BARCODE_FONT_SIZE,
    DEFAULT_BARCODE_MODULE_HEIGHT,
    DEFAULT_BARCODE_MODULE_WIDTH,
    DEFAULT_BARCODE_QUIET_ZONE,
)
from classroom_library_label_maker.logger import get_logger
from classroom_library_label_maker.models import ApplicationSettings
from classroom_library_label_maker.rendering.renderer import BarcodeSymbology

_logger = get_logger("rendering.python_barcode")


class PythonBarcodeRenderer:
    """Render barcode images using ``python-barcode`` and Pillow.

    Public methods accept and return only standard library / domain types so
    the service layer never imports vendor libraries.

    Rendering geometry comes from constructor arguments (typically sourced from
    :class:`ApplicationSettings`) rather than hardcoded call-site values.
    """

    def __init__(
        self,
        *,
        module_width: float = DEFAULT_BARCODE_MODULE_WIDTH,
        module_height: float = DEFAULT_BARCODE_MODULE_HEIGHT,
        quiet_zone: float = DEFAULT_BARCODE_QUIET_ZONE,
        font_size: int = DEFAULT_BARCODE_FONT_SIZE,
        dpi: int = DEFAULT_BARCODE_DPI,
    ) -> None:
        """Initialize renderer options.

        Args:
            module_width: Bar module width in millimeters.
            module_height: Bar module height in millimeters.
            quiet_zone: Quiet-zone margin in millimeters.
            font_size: Human-readable text size in points.
            dpi: Output image resolution.
        """
        self._module_width = module_width
        self._module_height = module_height
        self._quiet_zone = quiet_zone
        self._font_size = font_size
        self._dpi = dpi

    @classmethod
    def from_settings(cls, settings: ApplicationSettings) -> PythonBarcodeRenderer:
        """Build a renderer using values from :class:`ApplicationSettings`."""
        return cls(
            module_width=settings.barcode_module_width,
            module_height=settings.barcode_module_height,
            quiet_zone=settings.barcode_quiet_zone,
            font_size=settings.barcode_font_size,
            dpi=settings.barcode_dpi,
        )

    def _writer_options(self) -> dict[str, float | int]:
        """Return python-barcode ImageWriter options for the configured geometry."""
        return {
            "module_width": self._module_width,
            "module_height": self._module_height,
            "quiet_zone": self._quiet_zone,
            "font_size": self._font_size,
            "dpi": self._dpi,
        }

    def render_to_file(
        self,
        data: str,
        output_path: Path,
        *,
        symbology: BarcodeSymbology = BarcodeSymbology.EAN13,
    ) -> Path:
        """Render ``data`` as a barcode PNG at ``output_path``.

        Args:
            data: Payload to encode (normalized ISBN-13 digits for EAN-13).
            output_path: Destination image path (``.png`` expected).
            symbology: Target symbology. Only :attr:`BarcodeSymbology.EAN13`
                is supported in this release.

        Returns:
            ``output_path`` after a successful write.

        Raises:
            ValueError: If ``symbology`` is unsupported or ``data`` cannot be
                encoded as the requested symbology.
            OSError: If the image file cannot be written.
        """
        output_path = Path(output_path)
        _logger.debug(
            "Rendering barcode (data=%r, output_path=%s, symbology=%s)",
            data,
            output_path,
            symbology,
        )

        if symbology is not BarcodeSymbology.EAN13:
            raise ValueError(
                f"Unsupported symbology for PythonBarcodeRenderer: {symbology!s}"
            )

        try:
            from barcode import get_barcode_class
            from barcode.writer import ImageWriter
        except ImportError as exc:  # pragma: no cover - dependency is required
            raise ValueError(
                "python-barcode is required to render barcode images"
            ) from exc

        barcode_cls = get_barcode_class("ean13")
        try:
            writer = ImageWriter()
            self._ensure_writer_font(writer)
            barcode = barcode_cls(data, writer=writer)
        except Exception as exc:
            raise ValueError(f"Cannot encode EAN-13 barcode for data={data!r}") from exc

        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with output_path.open("wb") as handle:
                barcode.write(handle, options=self._writer_options())
        except OSError:
            self._remove_incomplete_output(output_path)
            raise
        except Exception as exc:
            self._remove_incomplete_output(output_path)
            raise ValueError(
                f"Failed writing EAN-13 barcode image to {output_path}"
            ) from exc

        if not output_path.is_file() or output_path.stat().st_size <= 0:
            self._remove_incomplete_output(output_path)
            raise OSError(f"Barcode render produced an empty file: {output_path}")

        size = output_path.stat().st_size
        _logger.debug("Rendered barcode to %s (%s bytes)", output_path, size)
        return output_path

    @staticmethod
    def _ensure_writer_font(writer: object) -> None:
        """Point ImageWriter at a loadable TTF when the default path is missing.

        Packaged builds must ship ``barcode/fonts/DejaVuSansMono.ttf``. If the
        default path is broken, try the font next to the installed ``barcode``
        package before Pillow raises ``cannot open resource``.
        """
        font_path = Path(getattr(writer, "font_path", ""))
        if font_path.is_file():
            return
        try:
            import barcode as barcode_package
        except ImportError:  # pragma: no cover - dependency is required
            return
        candidate = (
            Path(barcode_package.__file__).resolve().parent
            / "fonts"
            / "DejaVuSansMono.ttf"
        )
        if candidate.is_file():
            writer.font_path = str(candidate)  # type: ignore[attr-defined]
            _logger.debug("Using barcode font at %s", candidate)

    @staticmethod
    def _remove_incomplete_output(output_path: Path) -> None:
        """Delete a partial/empty PNG so retries are not skipped as existing."""
        try:
            if output_path.is_file():
                output_path.unlink()
        except OSError:
            _logger.debug("Could not remove incomplete barcode file %s", output_path)
