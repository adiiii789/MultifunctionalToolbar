import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QMainWindow, QSizePolicy, QScrollArea
)
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtCore import Qt, QPoint, QPropertyAnimation, QRect
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
            ("Button 3", self.handle_script3),
            ("Button 4", self.handle_script4),
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

    def handle_script3(self):
        print("Skript 3 gestartet")

    def handle_script4(self):
        print("Skript 4 gestartet")


from PyQt5.QtCore import QPropertyAnimation, QRect, QEasingCurve

class PopupWindow(QWidget, ButtonContentMixin):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowTitle("Skript Starter (Popup)")

        self.layout = QVBoxLayout(self)
        self.add_buttons(self.layout)

        screen = get_monitors()[0]
        self.width_size = int(screen.width * 0.15)  # Dynamische Größe: 15 % Breite
        self.height_size = int(screen.height * 0.5)  # Dynamische Größe: 50 % Höhe
        self.setFixedSize(self.width_size, self.height_size)

        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(500)  # Dauer der Animation
        self.animation.setEasingCurve(QEasingCurve.OutCubic)  # Sanfte Bewegung

    def show_popup(self):
        cursor_pos = QCursor.pos()
        start_x = cursor_pos.x()
        start_y = cursor_pos.y()

        end_x = start_x - self.width_size
        end_y = start_y - self.height_size

        # Startet die Animation von unterhalb der Maus
        self.animation.setStartValue(QRect(start_x, start_y + 50, self.width_size, self.height_size))
        self.animation.setEndValue(QRect(end_x, end_y, self.width_size, self.height_size))

        self.animation.start()  # Animation starten
        self.show()
        self.activateWindow()


class MainAppWindow(QMainWindow, ButtonContentMixin):
    def __init__(self, app):
        super().__init__()
        self.app = app
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
        self.setStyleSheet(dark_mode_stylesheet)

        self.popup = PopupWindow()
        self.main_window = MainAppWindow(self)

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon("TrayIcon.ico"))
        self.tray.setVisible(True)

        self.tray.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Context:
            self.popup.show_popup()  # Hier wird die Animation gestartet!
        elif reason == QSystemTrayIcon.Trigger:
            self.main_window.show()


if __name__ == "__main__":
    app = TrayApp(sys.argv)
    sys.exit(app.exec_())