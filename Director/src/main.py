"""Точка входа в приложение Director."""

import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from app.api import EngineClient, FileGatewayClient
from app.components import MainWindow
from app.store import AppStore, Action
from app.utils.styles import STYLESHEET


def main() -> int:
    """Главная функция запуска приложения."""
    app = QApplication(sys.argv)
    app.setApplicationName("Director")
    app.setApplicationDisplayName("Director")
    app.setStyleSheet(STYLESHEET)

    # Создаём клиенты для двух сервисов
    engine_client = EngineClient()  # порт 50051
    file_gateway_client = FileGatewayClient()  # порт 50052

    # Создаём реактивный store
    store = AppStore(engine_client, file_gateway_client)

    # Создаём и показываем главное окно
    window = MainWindow(store)
    window.show()

    # Инициируем подключение к обоим сервисам
    store.dispatch(Action.connect_engine_request())
    store.dispatch(Action.connect_file_gateway_request())

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
