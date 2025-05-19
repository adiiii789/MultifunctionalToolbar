import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton,
    QSystemTrayIcon, QStyle
)
from PyQt5.QtGui import QIcon, QCursor
from PyQt5.QtCore import Qt, QPoint
from screeninfo import get_monitors

class PopupWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Skript Starter")
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.btn1 = QPushButton("Skript 1")
        self.btn1.clicked.connect(lambda: print("Skript 1 gestartet"))
        self.layout.addWidget(self.btn1)

        self.btn2 = QPushButton("Skript 2")
        self.btn2.clicked.connect(lambda: print("Skript 2 gestartet"))
        self.layout.addWidget(self.btn2)

        self.resize_dynamic()

    def resize_dynamic(self):
        # Bildschirmgröße holen
        screen = get_monitors()[0]  # primärer Bildschirm
        screen_width = screen.width
        screen_height = screen.height

        # Größe relativ zum Bildschirm setzen
        width = 200  # fest (schmal)
        height = int(screen_height * 0.3)  # z. B. 30 % der Höhe

        self.setFixedSize(width, height)

        # Positionieren: rechts unten
        x = screen_width - width - 10  # 10px vom rechten Rand
        y = screen_height - height - 40  # 40px vom unteren Rand (Tray-Höhe unter Windows berücksichtigen)

        self.move(QPoint(x, y))


class TrayApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)

        self.popup = PopupWindow()

        # Tray Icon
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))  # Platzhalter-Icon
        self.tray.setVisible(True)

        # Signal verbinden
        self.tray.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Context:  # Rechtsklick
            self.show_popup()

    def show_popup(self):
        self.popup.resize_dynamic()
        self.popup.show()
        self.popup.activateWindow()


if __name__ == "__main__":
    app = TrayApp(sys.argv)
    sys.exit(app.exec_())
