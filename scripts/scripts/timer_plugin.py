from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout
from PyQt5.QtCore import QTimer

class PluginWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("TimerPlugin")
        layout = QVBoxLayout(self)
        title = QLabel("⏱️ Timer-Plugin")
        title.setStyleSheet("font-weight: bold; font-size: 16px;")
        layout.addWidget(title)
        self.label = QLabel("0 s")
        self.label.setStyleSheet("font-size: 24px;")
        layout.addWidget(self.label)
        btn_row = QHBoxLayout()
        start_btn = QPushButton("Start")
        stop_btn = QPushButton("Stop")
        reset_btn = QPushButton("Reset")
        btn_row.addWidget(start_btn)
        btn_row.addWidget(stop_btn)
        btn_row.addWidget(reset_btn)
        layout.addLayout(btn_row)
        self.timer = QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_time)
        self.seconds = 0
        start_btn.clicked.connect(self.timer.start)
        stop_btn.clicked.connect(self.timer.stop)
        reset_btn.clicked.connect(self.reset)
    def update_time(self):
        self.seconds += 1
        self.label.setText(f"{self.seconds} s")
    def reset(self):
        self.seconds = 0
        self.label.setText("0 s")
