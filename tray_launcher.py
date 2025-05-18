import sys
import threading
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageDraw

# Beispiel-Funktionen, die durch die Buttons aufgerufen werden
def script1():
    print("Skript 1 wird ausgeführt...")

def script2():
    print("Skript 2 wird ausgeführt...")

# GUI-Fenster
class ScriptWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Skript Starter")
        self.setGeometry(100, 100, 200, 150)

        layout = QVBoxLayout()
        btn1 = QPushButton("Starte Skript 1")
        btn1.clicked.connect(script1)
        layout.addWidget(btn1)

        btn2 = QPushButton("Starte Skript 2")
        btn2.clicked.connect(script2)
        layout.addWidget(btn2)

        self.setLayout(layout)

# Taskleiste-Icon-Logik
class TrayApp:
    def __init__(self):
        self.icon = Icon("Skriptstarter")
        self.app = QApplication(sys.argv)
        self.window = ScriptWindow()

        # Erstelle ein Icon-Bild
        self.icon.icon = self.create_image()
        self.icon.menu = Menu(
            MenuItem("Fenster öffnen", self.show_window),
            MenuItem("Beenden", self.exit_app)
        )

    def create_image(self):
        # Einfaches Icon generieren
        image = Image.new("RGB", (64, 64), "gray")
        draw = ImageDraw.Draw(image)
        draw.rectangle((16, 16, 48, 48), fill="black")
        return image

    def show_window(self, icon, item):
        self.window.show()

    def exit_app(self, icon, item):
        self.icon.stop()
        self.app.quit()

    def run(self):
        # Starte das Tray-Icon in einem eigenen Thread
        threading.Thread(target=self.icon.run, daemon=True).start()
        sys.exit(self.app.exec_())

if __name__ == "__main__":
    tray_app = TrayApp()
    tray_app.run()
