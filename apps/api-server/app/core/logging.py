import logging

class ConsoleHandler(logging.Handler):
    """Logging handler that forwards records to Cloudflare Worker's js.console methods."""
    def emit(self, record):
        try:
            import js
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                js.console.error(msg)
            elif record.levelno >= logging.WARNING:
                js.console.warn(msg)
            elif record.levelno >= logging.INFO:
                js.console.info(msg)
            else:
                js.console.log(msg)
        except Exception:
            import sys
            print(self.format(record), file=sys.stderr)


logger = logging.getLogger("paper_spells")

def setup_logging():
    handler = ConsoleHandler()
    handler.setFormatter(logging.Formatter("%(name)s: %(message)s"))
    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)
