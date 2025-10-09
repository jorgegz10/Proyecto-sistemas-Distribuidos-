from datetime import datetime, timedelta
from typing import Optional
from common.domain.tipos import estadoCircuit as CircuitState


class CircuitBreaker:
    """Circuit breaker sencillo en memoria.

    - El circuito se abre después de _threshold fallos consecutivos.
    - Tras _reset_timeout segundos en abierto, pasa a medio-abierto.
    - Un éxito resetea el contador y cierra el circuito.
    """

    _state: CircuitState = CircuitState.CERRADO
    _fail_count: int = 0
    _threshold: int = 3
    _last_opened: Optional[datetime] = None
    _reset_timeout: int = 10  # segundos

    @classmethod
    def is_open(cls) -> bool:
        if cls._state == CircuitState.ABIERTO:
            if cls._last_opened and (datetime.now() - cls._last_opened) > timedelta(seconds=cls._reset_timeout):
                cls._state = CircuitState.MEDIO_ABIERTO
        return cls._state == CircuitState.ABIERTO

    @classmethod
    def on_success(cls) -> None:
        cls._fail_count = 0
        cls._state = CircuitState.CERRADO

    @classmethod
    def on_failure(cls) -> None:
        cls._fail_count += 1
        if cls._fail_count >= cls._threshold:
            cls._state = CircuitState.ABIERTO
            cls._last_opened = datetime.now()

    @classmethod
    def force_open(cls) -> None:
        cls._state = CircuitState.ABIERTO
        cls._last_opened = datetime.now()

    @classmethod
    def force_close(cls) -> None:
        cls._state = CircuitState.CERRADO
        cls._fail_count = 0