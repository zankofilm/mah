# -*- coding: utf-8 -*-
import sys
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt

from client_ui import ClientApplicationController, configure_application


def main() -> int:
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)
    configure_application(app)
    try:
        controller = ClientApplicationController(app)
        app.setProperty("clientController", controller)
        controller.start()
        return app.exec_()
    except Exception as exc:
        QMessageBox.critical(None, "خطای راه‌اندازی", str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
