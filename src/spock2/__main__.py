"""CLI-Einstieg: ``python -m spock2`` bzw. Script ``spock2``."""

from __future__ import annotations


def main() -> None:
    """Startet die Anwendung."""
    from spock2.app import main as app_main

    raise SystemExit(app_main())


if __name__ == "__main__":
    main()
