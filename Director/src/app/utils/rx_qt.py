"""Утилиты для интеграции RxPY с PyQt6."""

from typing import Callable, Any, Optional
from functools import wraps

from PyQt6.QtCore import QObject, pyqtSignal, QMetaObject, Qt, Q_ARG
from PyQt6.QtWidgets import QApplication
from reactivex import Observable
from reactivex.disposable import Disposable, CompositeDisposable


class RxSlot(QObject):
    """
    Мост между RxPY Observable и Qt слотами.
    
    Гарантирует, что callback вызывается в главном потоке Qt.
    """

    _signal = pyqtSignal(object)

    def __init__(self, callback: Callable[[Any], None], parent: Optional[QObject] = None):
        super().__init__(parent)
        self._callback = callback
        self._signal.connect(self._on_signal)

    def _on_signal(self, value: Any) -> None:
        """Слот, вызываемый в главном потоке."""
        self._callback(value)

    def on_next(self, value: Any) -> None:
        """Безопасно эмитит значение в главный поток."""
        self._signal.emit(value)


def schedule_on_main_thread(callback: Callable[[], None]) -> None:
    """Запланировать выполнение callback в главном потоке Qt."""
    app = QApplication.instance()
    if app:
        QMetaObject.invokeMethod(
            app,
            callback,
            Qt.ConnectionType.QueuedConnection,
        )


class QtDisposableMixin:
    """
    Миксин для Qt виджетов, упрощающий управление подписками RxPY.
    
    Использование:
        class MyWidget(QWidget, QtDisposableMixin):
            def __init__(self):
                super().__init__()
                self.init_disposables()
                
                # Подписка с автоматической отпиской при уничтожении
                self.subscribe(
                    store.select(lambda s: s.projects),
                    self._on_projects_changed
                )
    """

    def init_disposables(self) -> None:
        """Инициализировать контейнер подписок."""
        self._disposables = CompositeDisposable()

    def subscribe(
        self,
        observable: Observable,
        on_next: Callable[[Any], None],
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> Disposable:
        """
        Подписаться на Observable с автоматическим выполнением в главном потоке.
        
        Подписка автоматически отменяется при вызове dispose_all().
        """
        slot = RxSlot(on_next, parent=self if isinstance(self, QObject) else None)

        def error_handler(e: Exception) -> None:
            if on_error:
                schedule_on_main_thread(lambda: on_error(e))
            else:
                print(f"[RxPY Error] {e}")

        disposable = observable.subscribe(
            on_next=slot.on_next,
            on_error=error_handler,
        )

        self._disposables.add(disposable)
        return disposable

    def dispose_all(self) -> None:
        """Отменить все подписки."""
        if hasattr(self, "_disposables"):
            self._disposables.dispose()


