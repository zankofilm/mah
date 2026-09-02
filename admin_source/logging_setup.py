# -*- coding: utf-8 -*-
"""پیکربندی ثبت خطاهای برنامه با چرخش فایل لاگ."""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from runtime_paths import get_logs_dir


def configure_logging(base_dir=None):
    log_dir = os.path.join(base_dir, "logs") if base_dir else get_logs_dir()
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "app.log")

    root = logging.getLogger()
    if getattr(root, "_javanrood_configured", False):
        return log_path
    root.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(threadName)s | %(name)s | %(message)s"
    )
    file_handler = RotatingFileHandler(
        log_path, maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)
    root._javanrood_configured = True
    logging.getLogger(__name__).info("logging initialized")
    return log_path


def install_exception_hook():
    original_hook = sys.excepthook

    def _hook(exc_type, exc_value, traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            original_hook(exc_type, exc_value, traceback)
            return
        logging.getLogger("uncaught").critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, traceback)
        )
        original_hook(exc_type, exc_value, traceback)

    sys.excepthook = _hook
