"""Точка входа в приложение Director."""

import sys

from PyQt6.QtWidgets import QApplication

from app.api import GatewayClient
from app.components import MainWindow
from app.store import AppStore, Action
from app.utils.styles import STYLESHEET


def main() -> int:
    """Главная функция запуска приложения."""
    app = QApplication(sys.argv)
    app.setApplicationName("Director")
    app.setApplicationDisplayName("Director")
    app.setStyleSheet(STYLESHEET)

    # Создаём клиент для API Gateway (единая точка входа)
    gateway = GatewayClient("[::1]:50050")

    # Создаём реактивный store
    store = AppStore(gateway)

    # Создаём и показываем главное окно
    window = MainWindow(store)
    window.show()

    # Инициируем подключение к API Gateway
    store.dispatch(Action.connect_request())

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
