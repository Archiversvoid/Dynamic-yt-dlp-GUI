"""Colors, shared stylesheets, fonts and app-wide Qt style helpers."""
import theme
from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QLineEdit, QProxyStyle, QScrollBar, QStyle


TEAL_ACCENT   = "#00BFA5"


BG_DARK       = "#121212"


SIDEBAR_DARK  = "#181818"


CARD_BG       = "#1E1E1E"


CARD_INNER_BG = "#282828"


INPUT_BG      = "#333333"


TEXT_MAIN     = "#FFFFFF"


TEXT_MUTED    = "#8A8A8A"


ERROR_RED     = "#FF5555"


ERROR_BG      = "#2A1515"


_FALLBACKS = None


def _fallback_families():
    """Fonts to try, in this order, when the main font lacks a glyph (emoji, CJK, symbols, other
    scripts in video titles). Without an explicit list Qt falls back to scanning EVERY installed
    font - on a machine with hundreds of fonts, some of them legacy raster fonts (Fixedsys...) that
    DirectWrite cannot open (the 'CreateFontFaceFromHDC() failed' lines in the console), that scan
    froze the Downloads tab for seconds. Only fonts that really exist are listed: asking for a
    missing family would trigger a slow lookup of its own."""
    global _FALLBACKS
    if _FALLBACKS is None:
        wanted = ("Segoe UI", "Segoe UI Emoji", "Segoe UI Symbol", "Microsoft YaHei UI", "Yu Gothic UI",
                  "Malgun Gothic", "Microsoft JhengHei UI", "Nirmala UI", "Leelawadee UI", "Arial")
        _FALLBACKS = [f for f in wanted if QFontDatabase.hasFamily(f)]
    return _FALLBACKS


def install_font_safety():
    """Call once at startup. If anything ever asks for a legacy raster font by name, hand Qt a real
    font instead of letting it try (and fail) to build a DirectWrite face for it."""
    for legacy, modern in (("Fixedsys", "Consolas"), ("Terminal", "Consolas"), ("System", "Segoe UI"),
                           ("Modern", "Segoe UI"), ("MS Sans Serif", "Segoe UI"), ("Small Fonts", "Segoe UI")):
        if QFontDatabase.hasFamily(modern):
            QFont.insertSubstitution(legacy, modern)


def _crisp_font(family, size, weight=None):
    """Roboto-Regular.ttf is the only weight actually embedded (see
    _setup_ui's QFontDatabase.addApplicationFont call) - every other
    weight Qt renders for "Roboto" is synthesized from it. On Windows,
    Qt/FreeType's default hinting combined with that synthesis is what
    produces the stray-pixel artifacts above letters like e/m/n/a (this
    never showed up in CustomTkinter, which uses native Windows text
    rendering, not FreeType). Disabling hinting and ClearType-style
    subpixel antialiasing - plain grayscale antialiasing instead - avoids
    the glyph distortion that triggers it."""
    f = QFont(family, size)
    f.setFamilies([family] + [x for x in _fallback_families() if x != family])
    if weight is not None: f.setWeight(weight)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    f.setStyleStrategy(QFont.StyleStrategy.PreferAntialias | QFont.StyleStrategy.NoSubpixelAntialias)
    return f


COMBO_QSS = """
    QComboBox { background-color: #1A1A1A; color: #FFFFFF; font-size: 14px; border-radius: 6px; padding: 5px 12px; border: 1px solid #2A2A2A; }
    QComboBox::drop-down { border: none; width: 0px; }
    QComboBox::down-arrow { image: none; border: none; }
    QComboBox QAbstractItemView { background-color: #181818; color: #FFFFFF; selection-background-color: #B5B5B5; selection-color: #000000; border: 1px solid #FFFFFF; border-radius: 4px; outline: none; padding: 2px 0px; }
    QComboBox QAbstractItemView::item { min-height: 26px; padding-left: 10px; color: #FFFFFF; }
    QComboBox QAbstractItemView::item:selected { background-color: #B5B5B5; color: #000000; }
"""


_MONO_FAMILY = None


def _mono_family():
    """A fixed-width font family that is actually installed. "monospace" and
    "sans-serif" are CSS generics, not real Windows fonts: when Qt is asked
    for a family that doesn't exist it searches by loading font files to
    resolve the name, which the startup profile measured at ~3.7 s for a
    single QPlainTextEdit. Always ask for a family that exists."""
    global _MONO_FAMILY
    if _MONO_FAMILY is None:
        for fam in ("Consolas", "Cascadia Mono", "Courier New"):
            if QFontDatabase.hasFamily(fam):
                _MONO_FAMILY = fam
                break
        else:
            _MONO_FAMILY = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()
    return _MONO_FAMILY


def _tint_overlay(alpha_dark, alpha_light):
    """Translucent fill used for hover/chip tints: white-on-dark, black-on-light."""
    return QColor(0, 0, 0, alpha_light) if theme.is_light() else QColor(255, 255, 255, alpha_dark)


def _hover_overlay():
    return _tint_overlay(18, 12)


def _white_sheen(alpha_dark, alpha_light):
    """The moving highlight on skeleton blocks: faint on dark, strong on light."""
    return QColor(255, 255, 255, alpha_light if theme.is_light() else alpha_dark)


class NoFocusRectStyle(QProxyStyle):
    """Suppresses the dotted keyboard-focus rectangle Windows draws on
    buttons/widgets after Alt (or Ctrl, in some apps) is pressed a couple
    times - toggling "keyboard cues" visibility is native Windows
    behavior, not something tied to one widget, so this is handled once
    at the style level rather than per-widget."""
    def drawPrimitive(self, element, option, painter, widget=None):
        if element == QStyle.PrimitiveElement.PE_FrameFocusRect:
            return
        super().drawPrimitive(element, option, painter, widget)


class GlobalContextMenuBlocker(QObject):
    """Blocks the native right-click/Menu-key flyout on every QLineEdit
    (Undo/Redo/Cut/Copy/Paste/Select All) and QScrollBar (Scroll Here/
    Top/Bottom/...) in the app, including ones created after this filter
    is installed - an app-wide event filter instead of a per-widget
    setContextMenuPolicy call, so nothing added later needs remembering."""
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ContextMenu and isinstance(obj, (QLineEdit, QScrollBar)):
            return True
        return super().eventFilter(obj, event)
