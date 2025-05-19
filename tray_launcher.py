import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QMainWindow, QSizePolicy
)
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtCore import Qt, QPoint
from screeninfo import get_monitors

# Dark Mode Stylesheet
dark_mode_stylesheet = """
    QWidget {
        background-color: #2E2E2E;
        color: #FFFFFF;
    }

    QPushButton {
        background-color: #3A3A3A;
        color: #FFFFFF;
        border: 1px solid #5A5A5A;
        padding: 8px;
    }

    QPushButton:hover {
        background-color: #505050;
    }
"""

# Light Mode Stylesheet
light_mode_stylesheet = """
    QWidget {
        background-color: #FFFFFF;
        color: #000000;
    }

    QPushButton {
        background-color: #DDDDDD;
        color: #000000;
        border: 1px solid #AAAAAA;
        padding: 8px;
    }

    QPushButton:hover {
        background-color: #CCCCCC;
    }
"""


class ButtonContentMixin:
    def add_buttons(self, layout):
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        for label, handler in [
            ("Button 1", self.handle_script1),
            ("Button 2", self.handle_script2),
        ]:
            button = QPushButton(label)
            button.setMinimumHeight(60)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.setStyleSheet("QPushButton { margin: 0px; padding: 0px; }")

            layout.addWidget(button)
            button.clicked.connect(handler)

    def handle_script1(self):
        print("Skript 1 gestartet")

    def handle_script2(self):
        print("Skript 2 gestartet")


class PopupWindow(QWidget, ButtonContentMixin):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowTitle("Skript Starter (Popup)")

        self.layout = QVBoxLayout(self)
        self.add_buttons(self.layout)

        self.setFixedSize(200, 150)

    def position_at_cursor_bottom_right(self):
        cursor_pos = QCursor.pos()
        x = cursor_pos.x() - self.width()
        y = cursor_pos.y() - self.height()
        self.move(QPoint(x, y))


class MainAppWindow(QMainWindow, ButtonContentMixin):
    def __init__(self, app):
        super().__init__()
        self.app = app  # Referenz auf die QApplication
        self.setWindowTitle("Skript Starter – Hauptfenster")
        self.resize(800, 600)

        central_widget = QWidget()
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignTop)

        self.add_buttons(layout)

        # Theme-Wechsel Button
        self.toggle_button = QPushButton("Wechsle Theme")
        self.toggle_button.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.toggle_button.clicked.connect(self.toggle_theme)
        layout.addWidget(self.toggle_button)

        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        self.dark_mode = True  # Start im Dark Mode

    def toggle_theme(self):
        if self.dark_mode:
            self.app.setStyleSheet(light_mode_stylesheet)
            self.dark_mode = False
        else:
            self.app.setStyleSheet(dark_mode_stylesheet)
            self.dark_mode = True


class TrayApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)

        self.setStyleSheet(dark_mode_stylesheet)  # Startet mit Dark Mode

        self.popup = PopupWindow()
        self.main_window = MainAppWindow(self)  # Hauptfenster bekommt App-Referenz

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon("TrayIcon.ico"))
        self.tray.setVisible(True)

        self.tray.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Context:
            self.show_popup()
        elif reason == QSystemTrayIcon.Trigger:
            self.show_main_window()

    def show_popup(self):
        self.popup.position_at_cursor_bottom_right()
        self.popup.show()
        self.popup.activateWindow()

    def show_main_window(self):
        self.main_window.show()
        self.main_window.activateWindow()
        self.main_window.raise_()


if __name__ == "__main__":
    app = TrayApp(sys.argv)
    sys.exit(app.exec_())