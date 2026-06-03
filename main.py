"""Axrlen Polymarket automated betting bot entrypoint."""

from __future__ import annotations

import logging
import signal
import sys
import time

from axrlen.config import ensure_data_dirs, load_settings
from axrlen.health import record_cycle, start_health_server
from axrlen.workflow.pipeline import WorkflowPipeline

logger = logging.getLogger(__name__)
_shutdown = False


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stdout,
    )


def _handle_signal(signum: int, _frame) -> None:
    global _shutdown
    logger.info("Received signal %s — shutting down gracefully", signum)
    _shutdown = True


def main() -> None:
    settings = load_settings()
    _configure_logging(settings.log_level)
    ensure_data_dirs()

    logger.info(
        "Axrlen Polymarket bot starting | paper=%s live=%s | interval=%dm | categories=%s",
        settings.paper_trading,
        settings.is_live,
        settings.scan_interval_minutes,
        ",".join(settings.market_categories),
    )

    start_health_server(settings.health_port)
    pipeline = WorkflowPipeline(settings)

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    while not _shutdown:
        try:
            results = pipeline.run_cycle()
            record_cycle(len(results))
            logger.info("Cycle complete — processed %d markets", len(results))
        except Exception as exc:
            logger.exception("Cycle failed: %s", exc)

        for _ in range(settings.scan_interval_minutes * 60):
            if _shutdown:
                break
            time.sleep(1)

    logger.info("Axrlen bot stopped")


if __name__ == "__main__":
    main()
