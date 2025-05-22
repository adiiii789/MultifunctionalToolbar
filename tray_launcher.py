import sys
import os
import subprocess
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QMainWindow, QSizePolicy
)
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve
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
        # Prüfe Layout-Typ zur Sicherheit
        # print(f"Layout ist vom Typ: {type(layout)}")

        # Alle Widgets aus Layout entfernen (Buttons etc)
        for i in reversed(range(layout.count())):
            widget = layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)

        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        # Zurück-Button nur anzeigen, wenn nicht im Stammordner
        if self.current_path != os.path.abspath(self.SCRIPT_FOLDER):
            back_button = QPushButton("⬅️ Zurück")
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
                continue  # Andere Dateien ignorieren

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
        # Nur zurück bis zum Script-Ordner
        if os.path.commonpath([parent, root]) == root:
            self.current_path = parent
            self.add_buttons(self.layout)

    def run_script(self, path):
        try:
            subprocess.Popen([sys.executable, path])
            print(f"{path} gestartet.")
        except Exception as e:
            print(f"Fehler beim Starten von {path}: {e}")

    def update_button_styles(self, layout):
        dark_mode = getattr(self, "dark_mode", True)
        for i in range(layout.count()):
            button = layout.itemAt(i).widget()
            if isinstance(button, QPushButton):
                if button.objectName() == "back_button":
                    button.setStyleSheet(f"""
                        QPushButton {{
                            background-color: {'#444444' if dark_mode else '#CCCCCC'};
                            color: {'#FFFFFF' if dark_mode else '#000000'};
                            border: 1px solid #666666;
                            padding: 8px;
                            margin-bottom: 4px;
                        }}
                        QPushButton:hover {{
                            background-color: {'#555555' if dark_mode else '#BBBBBB'};
                        }}
                    """)
                else:
                    entry_type = button.property("entry_type")
                    if entry_type == "folder":
                        button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#3A4A5A' if dark_mode else '#DDEEFF'};
                                color: {'#FFFFFF' if dark_mode else '#000000'};
                                border: 1px solid #5A5A5A;
                                padding: 8px;
                            }}
                            QPushButton:hover {{
                                background-color: {'#4B5B6B' if dark_mode else '#CCE5FF'};
                            }}
                        """)
                    elif entry_type == "file":
                        button.setStyleSheet(f"""
                            QPushButton {{
                                background-color: {'#3A3A3A' if dark_mode else '#DDDDDD'};
                                color: {'#FFFFFF' if dark_mode else '#000000'};
                                border: 1px solid #5A5A5A;
                                padding: 8px;
                            }}
                            QPushButton:hover {{
                                background-color: {'#505050' if dark_mode else '#CCCCCC'};
                            }}
                        """)


class PopupWindow(QWidget, ButtonContentMixin):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowTitle("Skript Starter (Popup)")

        self.layout = QVBoxLayout(self)  # WICHTIG: keine Klammern bei self.layout
        self.init_button_state()
        self.add_buttons(self.layout)

        screen = get_monitors()[0]
        self.width_size = int(screen.width * 0.15)  # 15% Bildschirmbreite
        self.height_size = int(screen.height * 0.5)  # 50% Bildschirmhöhe
        self.setFixedSize(self.width_size, self.height_size)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(500)
        self.animation.setEasingCurve(QEasingCurve.OutCubic)

        self.dark_mode = True  # Standard Dark Mode

    def show_popup(self):
        # Buttons neu laden, damit ggf. geöffnete Ordner und Theme aktuell sind
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
        event.ignore()  # Verhindert das Schließen
        self.hide()


class MainAppWindow(QMainWindow, ButtonContentMixin):
    def __init__(self, app, popup=None):
        super().__init__()
        self.app = app
        self.popup = popup  # Referenz zum Popup
        self.setWindowTitle("Skript Starter – Hauptfenster")
        self.resize(800, 600)

        central_widget = QWidget()
        self.layout = QVBoxLayout(central_widget)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setAlignment(Qt.AlignTop)

        self.init_button_state()
        self.add_buttons(self.layout)

        self.toggle_button = QPushButton("Wechsle Theme")
        self.toggle_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.toggle_button.clicked.connect(self.toggle_theme)
        self.layout.addWidget(self.toggle_button)

        central_widget.setLayout(self.layout)
        self.setCentralWidget(central_widget)

        self.dark_mode = True  # Start mit Dark Mode

    def toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.app.setStyleSheet(dark_mode_stylesheet if self.dark_mode else light_mode_stylesheet)
        self.update_button_styles(self.layout)
        # Popup auch updaten, falls vorhanden
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
            self.main_window.show()


if __name__ == "__main__":
    app = TrayApp(sys.argv)
    sys.exit(app.exec_())
