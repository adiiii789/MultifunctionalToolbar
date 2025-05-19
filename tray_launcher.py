import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QStyle, QMainWindow, QSizePolicy
)
from PyQt5.QtGui import QCursor, QIcon
from PyQt5.QtCore import Qt, QPoint
from screeninfo import get_monitors

class ButtonContentMixin:
    def add_buttons(self, layout):
        btn1 = QPushButton("Skript 1")
        btn1.clicked.connect(lambda: print("Skript 1 gestartet"))
        layout.addWidget(btn1)

        btn2 = QPushButton("Skript 2")
        btn2.clicked.connect(lambda: print("Skript 2 gestartet"))
        layout.addWidget(btn2)

class PopupWindow(QWidget, ButtonContentMixin):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)
        self.setWindowTitle("Skript Starter (Popup)")

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.add_buttons(self.layout)

    def resize_dynamic(self):
        screen = get_monitors()[0]
        screen_width = screen.width
        screen_height = screen.height

        width = int(screen_width * 0.15)
        height = int(screen_height * 0.5)
        self.setFixedSize(width, height)

    def position_at_cursor_bottom_right(self):
        cursor_pos = QCursor.pos()
        x = cursor_pos.x() - self.width()
        y = cursor_pos.y() - self.height()
        self.move(QPoint(x, y))


class MainAppWindow(QMainWindow, ButtonContentMixin):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Skript Starter – Hauptfenster")
        self.resize(500, 400)

        central_widget = QWidget()
        layout = QVBoxLayout()
        self.add_buttons(layout)
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)


class TrayApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)

        self.popup = PopupWindow()
        self.main_window = MainAppWindow()

        self.tray = QSystemTrayIcon()
        self.tray.setIcon(QIcon("TrayIcon.ico"))
        self.tray.setVisible(True)

        self.tray.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Context:  # Rechtsklick
            self.show_popup()
        elif reason == QSystemTrayIcon.Trigger:  # Linksklick
            self.show_main_window()

    def show_popup(self):
        self.popup.resize_dynamic()
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
