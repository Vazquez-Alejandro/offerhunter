import time
import signal
import sys

from engine import start_engine


def main():
    print("🟢 OfferHunter worker starting...")

    # Arranca el engine (scheduler interno)
    start_engine(run_once=True)

    # Mantener vivo el proceso
    while True:
        time.sleep(3600)


def _handle_exit(signum, frame):
    print(f"🛑 Worker received signal {signum}. Shutting down...")
    sys.exit(0)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, _handle_exit)
    signal.signal(signal.SIGTERM, _handle_exit)

    main()