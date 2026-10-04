# =============================================================================
# Demo: Normaler Button mit Parametern — halbtransparent, eigene Höhe,
# eigener Name/Icon. Erscheint nur im Hauptfenster (nicht im Popup).
# =============================================================================
NAME = "Notizen (Demo)"
ICON = "📝"
BUTTON_HEIGHT = 48
OPACITY = 0.75
ALLOW_POPUP = False

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLabel


class PluginWidget(QWidget):
    def __init__(self, mode='Window'):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel('📝 Schnellnotizen')
        title.setStyleSheet('font-weight: bold; font-size: 16px;')
        layout.addWidget(title)
        self.edit = QTextEdit()
        self.edit.setPlaceholderText('Notiz eingeben...')
        layout.addWidget(self.edit)
