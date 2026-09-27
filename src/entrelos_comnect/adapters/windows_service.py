from __future__ import annotations

import time
from collections.abc import Callable


def run_worker_loop(run_once: Callable[[], bool], *, idle_seconds: float = 5.0) -> None:
    """Loop cooperativo usado pelo host Windows; todo I/O é iniciado pelo Comnect."""
    while True:
        if not run_once():
            time.sleep(idle_seconds)


def create_windows_service(run_once: Callable[[], bool]) -> type:
    """Cria a classe pywin32 sob demanda para manter o domínio independente do Windows."""
    try:
        import win32event
        import win32service
        import win32serviceutil
    except ImportError as error:
        raise RuntimeError("install the windows-service extra on Windows") from error

    class EntrelosComnectWindowsService(win32serviceutil.ServiceFramework):
        _svc_name_ = "EntrelosComnect"
        _svc_display_name_ = "Entrelos Comnect"
        _svc_description_ = "Conector Entrelos com conexões de saída mTLS."

        def __init__(self, args: list[str]) -> None:
            super().__init__(args)
            self._stop_event = win32event.CreateEvent(None, 0, 0, None)

        def SvcStop(self) -> None:  # noqa: N802
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop_event)

        def SvcDoRun(self) -> None:  # noqa: N802
            while (
                win32event.WaitForSingleObject(self._stop_event, 1_000) != win32event.WAIT_OBJECT_0
            ):
                run_once()

    return EntrelosComnectWindowsService
