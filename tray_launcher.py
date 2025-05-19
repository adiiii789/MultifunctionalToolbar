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
        self.setFixedSize(200, 120)
        self.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint)

        layout = QVBoxLayout()
        btn1 = QPushButton("Skript 1")
        btn1.clicked.connect(lambda: print("Skript 1 gestartet"))
        layout.addWidget(btn1)

        btn2 = QPushButton("Skript 2")
        btn2.clicked.connect(lambda: print("Skript 2 gestartet"))
        layout.addWidget(btn2)

        self.setLayout(layout)

class TrayApp(QApplication):
    def __init__(self, sys_argv):
        super().__init__(sys_argv)
        self.setQuitOnLastWindowClosed(False)

        self.popup = PopupWindow()

        # Tray Icon
        self.tray = QSystemTrayIcon()
        self.tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon)) # FÜr später, Icon ersetzen
        self.tray.setVisible(True)

        # Signal verbinden
        self.tray.activated.connect(self.on_tray_activated)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Context:  # Rechtsklick
            self.show_popup()

    from PyQt5.QtGui import QCursor

    def show_popup(self):
        cursor_pos = QCursor.pos()
        x = cursor_pos.x() - self.popup.width() + 20
        y = cursor_pos.y() - self.popup.height() - 10
        self.popup.move(QPoint(x, y))
        self.popup.show()
        self.popup.activateWindow()


if __name__ == "__main__":
    app = TrayApp(sys.argv)
    sys.exit(app.exec_())
