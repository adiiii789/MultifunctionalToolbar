import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QMainWindow, QSizePolicy, QHBoxLayout, QLabel
)
from PyQt5.QtGui import QCursor, QIcon, QMouseEvent
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, QPoint
from screeninfo import get_monitors

# Dark Mode Stylesheet
dark_mode_stylesheet = """
    QWidget {
        background-color: #2E2E2E;
        color: #FFFFFF;
    }
"""

# Light Mode Stylesheet
light_mode_stylesheet = """
    QWidget {
        background-color: #FFFFFF;
        color: #000000;
    }
"""


class ButtonContentMixin:
    SCRIPT_FOLDER = "scripts"

    def init_button_state(self):
        self.current_path = os.path.abspath(self.SCRIPT_FOLDER)
        if not os.path.exists(self.current_path):
            os.makedirs(self.current_path)

    def add_buttons(self, layout):
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        if self.current_path != os.path.abspath(self.SCRIPT_FOLDER):
            back_button = QPushButton("← Zurück")
            back_button.clicked.connect(self.go_back)
            back_button.setObjectName("back_button")
            layout.addWidget(back_button)

        entries = sorted(os.listdir(self.current_path))
        for entry in entries:
            full_path = os.path.join(self.current_path, entry)

            if os.path.isdir(full_path):
                button = QPushButton(f"[Ordner] {entry}")
                button.clicked.connect(lambda _, p=full_path: self.enter_directory(p))
                button.setProperty("entry_type", "folder")
            elif entry.endswith(".py"):
                button = QPushButton(entry)
                button.clicked.connect(lambda _, p=full_path: self.run_script(p))
                button.setProperty("entry_type", "file")
            else:
                continue

            button.setMinimumHeight(60)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layout.addWidget(button)

        self.update_button_styles(layout)

    def enter_directory(self, path):
        self.current_path = path
        self.add_buttons(self.layout)

    def go_back(self):
        parent = os.path.dirname(self.current_path)
        root = os.path.abspath(self.SCRIPT_FOLDER)
        if os.path.commonpath([parent, root]) == root:
            self.current_path = parent
            self.add_buttons(self.layout)

    def run_script(self, path):
        try:
            subprocess.Popen([sys.executable, path])
        except Exception as e:
            print(f"Fehler beim Starten von {path}: {e}")

    def update_button_styles(self, layout):
        dark_mode = getattr(self, "dark_mode", True)
        for i in range(layout.count()):
            button = layout.itemAt(i).widget()
            if isinstance(button, QPushButton):
                if button.objectName() == "back_button":
                    button.setMinimumHeight(40)
                    button.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {'#666666' if dark_mode else '#BBBBBB'};
                            color: {'#FFFFFF' if dark_mode else '#000000'};
                            font-weight: bold;
                        }}
                        QPushButton:hover {{
                            background-color: {'#777777' if dark_mode else '#CCCCCC'};
                        }}
                    """)
                else:
                    entry_type = button.property("entry_type")
                    if entry_type == "folder":
                        button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#3A4A6A' if dark_mode else '#DDDDFF'};
                                color: {'#FFFFFF' if dark_mode else '#000000'};
                            }}
                            QPushButton:hover {{
                                background-color: {'#4B5B6B' if dark_mode else '#CCCCEE'};
                            }}
                        """)
                    elif entry_type == "file":
                        button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#3A3A3A' if dark_mode else '#EEEEEE'};
                                color: {'#FFFFFF' if dark_mode else '#000000'};
                            }}
                            QPushButton:hover {{
                                background-color: {'#505050' if dark_mode else '#DDDDDD'};
                            }}
                        """)

class CustomTitleBar(QWidget):
    def __init__(self, parent, title=""):
        super().__init__(parent)
        self.parent = parent
        self.setFixedHeight(30)
        self.setStyleSheet("background-color: transparent")

        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(5, 0, 5, 0)

        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold")

        self.minimize_button = QPushButton("▁")
        self.minimize_button.setFixedSize(30, 28)
        self.minimize_button.setStyleSheet(self.button_style())
        self.minimize_button.clicked.connect(self.parent.showMinimized)

        self.maximize_button = QPushButton("▢")
        self.maximize_button.setFixedSize(30, 28)
        self.maximize_button.setStyleSheet(self.button_style())
        self.maximize_button.clicked.connect(self.toggle_maximize_restore)

        self.close_button = QPushButton("✕")
        self.close_button.setFixedSize(30, 28)
        self.close_button.setStyleSheet(self.button_style(close=True))
        self.close_button.clicked.connect(parent.close)

        self.layout.addWidget(self.title_label)
        self.layout.addStretch()
        self.layout.addWidget(self.minimize_button)
        self.layout.addWidget(self.maximize_button)
        self.layout.addWidget(self.close_button)

        self.old_pos = None

    def button_style(self, close=False):
        base = """
            QPushButton {
                border: none;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: %s;
            }
        """
        if close:
            hover_color = "#E81123"  # Rotes Hover für Close
        else:
            hover_color = "#CCCCCC"  # Graues Hover für andere Buttons
        return base % hover_color

    def toggle_maximize_restore(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
            self.maximize_button.setText("▢")
        else:
            self.parent.showMaximized()
            self.maximize_button.setText("❐")

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.old_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.old_pos is not None:
            delta = QPoint(event.globalPos() - self.old_pos)
            self.parent.move(self.parent.pos() + delta)
            self.old_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.old_pos = None


class PopupWindow(QWidget, ButtonContentMixin):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)

        self.layout = QVBoxLayout(self)
        self.init_button_state()
        self.add_buttons(self.layout)

        screen = get_monitors()[0]
        self.width_size = int(screen.width * 0.15)
        self.height_size = int(screen.height * 0.5)
        self.setFixedSize(self.width_size, self.height_size)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(500)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

        self.dark_mode = True

    def show_popup(self):
        self.add_buttons(self.layout)
        self.update_button_styles(self.layout)

        cursor_pos = QCursor.pos()
        start_x = cursor_pos.x()
        start_y = cursor_pos.y()
        end_x = start_x - self.width_size
        end_y = start_y - self.height_size

        self.animation.setStartValue(QRect(start_x, start_y + 50, self.width_size, self.height_size))
        self.animation.setEndValue(QRect(end_x, end_y, self.width_size, self.height_size))
        self.animation.start()
        self.show()
        self.activateWindow()

    def closeEvent(self, event):
        event.ignore()
        self.hide()


class MainAppWindow(QMainWindow, ButtonContentMixin):
    def __init__(self, app, popup=None):
        super().__init__()
        self.app = app
        self.popup = popup

        self.dark_mode = True

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setMinimumSize(800, 600)

        self.central = QWidget()
        self.central_layout = QVBoxLayout(self.central)
        self.central_layout.setContentsMargins(0, 0, 0, 0)

        self.title_bar = CustomTitleBar(self, "Skript Starter – Hauptfenster")
        self.central_layout.addWidget(self.title_bar)

        # Toggle-Button bleibt oben sichtbar
        self.toggle_button = QPushButton("Wechsle Theme")
        self.toggle_button.clicked.connect(self.toggle_theme)
        self.central_layout.addWidget(self.toggle_button)

        # Separater Container für Skript-Buttons
        self.button_container = QWidget()
        self.layout = QVBoxLayout(self.button_container)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        self.central_layout.addWidget(self.button_container)

        self.setCentralWidget(self.central)

        # Init Buttons
        self.init_button_state()
        self.add_buttons(self.layout)

        # Theme setzen
        self.toggle_theme()

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.app.setStyleSheet(dark_mode_stylesheet if self.dark_mode else light_mode_stylesheet)
        self.update_button_styles(self.layout)
        if self.popup:
            self.popup.dark_mode = self.dark_mode
            self.popup.update_button_styles(self.popup.layout)


class TrayApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)
        self.setStyleSheet(dark_mode_stylesheet)

        self.popup = PopupWindow()
        self.main_window = MainAppWindow(self, popup=self.popup)

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon("TrayIcon.ico"))
        self.tray.setVisible(True)

        self.tray.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Context:
            self.popup.show_popup()
        elif reason == QSystemTrayIcon.Trigger:
            # Linksklick auf Tray-Icon: Fenster anzeigen oder in den Vordergrund holen
            if self.main_window.isMinimized() or not self.main_window.isVisible():
                self.main_window.showNormal()   # Fenster wiederherstellen, falls minimiert
                self.main_window.activateWindow()
                self.main_window.raise_()
            else:
                # Wenn schon sichtbar, einfach in den Vordergrund bringen
                self.main_window.activateWindow()
                self.main_window.raise_()


if __name__ == "__main__":
    app = TrayApp(sys.argv)
    sys.exit(app.exec_())
