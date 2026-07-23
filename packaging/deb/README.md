# SPOCK2 als `.deb` bauen

Ziel: Ubuntu **24.04** (Latitude 5285 / Vagrant-VM). Primärlieferung laut ADR 0009.

## Voraussetzungen (Build-Host oder VM)

```bash
sudo apt update
sudo apt install -y \
  build-essential debhelper dh-python python3-all python3-setuptools \
  python3-pip python3-venv python3-wheel \
  dpkg-dev fakeroot
```

Python 3.12+ und Netzwerk für Pip-Deps (PySide6 u. a.) beim Wheel-Build.

## Schnellweg: Wheel + `fpm` / manuelles Layout (Dev)

Aus dem **Repo-Root**:

```bash
python3 -m venv .venv-build
source .venv-build/bin/activate
pip install -U pip build wheel
pip install -e ".[cups]"
python -m build --wheel

# Binary liegt nach pip install unter .venv-build/bin/spock2
# Für ein echtes .deb siehe unten (dh) oder:
```

## Empfohlen: `dpkg-buildpackage` über `packaging/deb`

Das `debian/`-Verzeichnis liegt unter `packaging/deb/debian/`. debhelper erwartet
üblicherweise `debian/` im Source-Root. Zwei praktikable Varianten:

### Variante A — Symlink im Repo-Root (einfach)

```bash
cd /pfad/zu/SPOCK2
ln -sfn packaging/deb/debian debian
dpkg-buildpackage -us -uc -b
# Ergebnis eine Ebene höher: ../spock2_0.1.0-1_*.deb
```

`debian/rules` installiert das Wheel nach `usr/`, plus udev/systemd/Kiosk/Config-Example.

### Variante B — Build nur in der Vagrant-VM

```bash
vagrant up
vagrant ssh -c 'cd /vagrant && ln -sfn packaging/deb/debian debian && dpkg-buildpackage -us -uc -b'
```

## Installation auf dem Zielgerät

```bash
sudo apt install -y ./spock2_0.1.0-1_amd64.deb
# oder:
sudo dpkg -i spock2_0.1.0-1_amd64.deb
sudo apt-get install -f   # fehlende Depends nachziehen
```

Nachinstallieren:

```bash
sudo cp /etc/spock2/spock2.toml.example /etc/spock2/spock2.toml
sudoedit /etc/spock2/spock2.toml
# Serials in udev-Regeln eintragen, neu laden:
sudo udevadm control --reload-rules && sudo udevadm trigger
# CUPS-Queues: siehe /usr/share/doc/spock2/cups-README.md
```

User-Service (Kiosk):

```bash
systemctl --user daemon-reload
systemctl --user enable --now spock2.service
# oder Autostart: ~/.config/autostart/spock2.desktop
```

## Hinweise

- Live-Config unter `/etc/spock2/spock2.toml` wird vom Paket **nicht** überschrieben (nur `.example`).
- `pycups` / native CUPS-Libs: ggf. `python3-cups` aus Ubuntu nutzen oder Pip-Extra `[cups]` im Build berücksichtigen.
- Version in `pyproject.toml` und `debian/changelog` synchron halten.

Siehe auch: `deploy/cups/README.md`.
