"""Shared GUI presentation tokens — colors and typography.

Presentation only. Home and Ready to Print (and status coloring) import these
constants so both screens share one restrained visual language. Do not put
workflow or business logic here.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Colors (near-neutral; tuned for contrast on white / light system chrome)
# ---------------------------------------------------------------------------

# Primary headings (product name, section titles, file-type headings).
COLOR_HEADING = "#0a0a0a"

# Body copy and explanatory sentences.
COLOR_BODY = "#2c2c2c"

# Secondary text (taglines, section captions) — muted but AA-readable.
COLOR_SECONDARY = "#3d3d3d"

# Filenames and path labels — readable without competing with headings.
COLOR_FILENAME = "#3d3d3d"

# Footer / de-emphasized chrome (version).
COLOR_MUTED = "#5c5c5c"

# Semantic status (success / attention / error).
COLOR_SUCCESS = "#0a5c0a"
COLOR_WARNING = "#7a5200"
COLOR_ERROR = "#8f210f"

# ---------------------------------------------------------------------------
# Typography scale (px in Qt stylesheets; platform default family)
# ---------------------------------------------------------------------------

FONT_PRODUCT_TITLE_PX = 24
FONT_PAGE_HEADLINE_PX = 28
FONT_SUBTITLE_PX = 13
FONT_BODY_PX = 15
FONT_SECTION_CAPTION_PX = 13
FONT_FILE_HEADING_PX = 13
FONT_FILENAME_PX = 13
FONT_VERSION_PX = 11
FONT_PRIMARY_ACTION_PX = 14
FONT_STATUS_PX = 13

# Shared page chrome (Home + Ready to Print).
PAGE_MARGIN_H = 32
PAGE_MARGIN_TOP = 28
PAGE_MARGIN_BOTTOM = 24
PAGE_SECTION_SPACING = 18


def status_color(level: str) -> str:
    """Return the semantic color for a status ``level`` (ok/warning/error)."""
    mapping = {
        "ok": COLOR_SUCCESS,
        "warning": COLOR_WARNING,
        "error": COLOR_ERROR,
    }
    return mapping.get(level, COLOR_SUCCESS)


def product_title_stylesheet() -> str:
    """Home header product name."""
    return (
        f"font-size: {FONT_PRODUCT_TITLE_PX}px; font-weight: 700; "
        f"color: {COLOR_HEADING};"
    )


def product_subtitle_stylesheet() -> str:
    """Home header tagline (visually secondary)."""
    return f"font-size: {FONT_SUBTITLE_PX}px; color: {COLOR_SECONDARY};"


def version_footer_stylesheet() -> str:
    """Muted version label."""
    return f"font-size: {FONT_VERSION_PX}px; color: {COLOR_MUTED};"


def primary_action_stylesheet(object_name: str) -> str:
    """Emphasized primary button (e.g. Generate Labels)."""
    return (
        f"QPushButton#{object_name} {{"
        f"font-size: {FONT_PRIMARY_ACTION_PX}px; font-weight: 600; "
        f"padding: 8px 20px;}}"
    )


def completion_headline_stylesheet(*, attention: bool = False) -> str:
    """Ready to Print success / attention headline."""
    color = COLOR_WARNING if attention else COLOR_SUCCESS
    return (
        f"font-size: {FONT_PAGE_HEADLINE_PX}px; font-weight: 700; "
        f"color: {color};"
    )


def completion_details_stylesheet() -> str:
    """Short explanatory summary under the headline."""
    return (
        f"font-size: {FONT_BODY_PX}px; color: {COLOR_BODY}; "
        f"padding-top: 2px; padding-bottom: 4px;"
    )


def completion_files_caption_stylesheet() -> str:
    """Files Created section heading."""
    return (
        f"font-size: {FONT_SECTION_CAPTION_PX}px; font-weight: 600; "
        f"color: {COLOR_SECONDARY}; margin-top: 10px;"
    )


def completion_file_heading_stylesheet() -> str:
    """Label Workbook / Updated Inventory headings."""
    return (
        f"font-size: {FONT_FILE_HEADING_PX}px; font-weight: 600; "
        f"color: {COLOR_HEADING};"
    )


def completion_filename_stylesheet() -> str:
    """Generated filenames (selectable; secondary to headings)."""
    return f"font-size: {FONT_FILENAME_PX}px; font-weight: 400; color: {COLOR_FILENAME};"


def home_group_box_stylesheet() -> str:
    """Consistent Files / Options / Actions section title weight."""
    return (
        f"QGroupBox {{ font-weight: 600; color: {COLOR_HEADING}; "
        f"margin-top: 8px; padding-top: 10px; }}"
        f"QGroupBox::title {{ subcontrol-origin: margin; "
        f"left: 10px; padding: 0 4px; }}"
    )


def status_label_stylesheet(level: str) -> str:
    """Home Actions status line color + readable size."""
    return (
        f"font-size: {FONT_STATUS_PX}px; color: {status_color(level)};"
    )
