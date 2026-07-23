# SPOCK2 RPM (optional)

Primärziel bleibt **Debian/Ubuntu `.deb`** (`packaging/deb/`). Dieses RPM-Skelett
ist für Fedora/RHEL-ähnliche Systeme gedacht und noch nicht produktionsreif.

## Build (Skizze)

```bash
# Abhängigkeiten (Fedora-Beispiel)
sudo dnf install -y rpm-build rpmdevtools python3-devel python3-pip python3-wheel

# Tarball aus Git erzeugen oder _sourcedir auf Repo zeigen
cd /pfad/zu/SPOCK2
# Spec anpassen (%prep/%setup), dann:
rpmbuild -ba packaging/rpm/spock2.spec \
  --define "_sourcedir $PWD" \
  --define "_rpmdir $PWD/packaging/rpm/out"
```

## Nach Installation

- Config-Beispiel: `/etc/spock2/spock2.toml.example` → nach `spock2.toml` kopieren
- udev: `udevadm control --reload-rules && udevadm trigger`
- CUPS-Queues wie in `deploy/cups/README.md`
- User-Unit: `systemctl --user enable --now spock2`

## Hinweise

- PySide6 und `pycups` können architekturabhängige Wheels brauchen — `BuildArch: noarch` ggf. entfernen.
- `%license LICENSE` setzt voraus, dass eine `LICENSE`-Datei im Repo liegt.
- Für typische Event-Kiosks Ubuntu 24.04 + `.deb` bevorzugen.
