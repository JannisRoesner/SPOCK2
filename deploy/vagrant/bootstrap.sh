#!/usr/bin/env bash
# SPOCK2 Vagrant Bootstrap — Ubuntu 24.04 für Windows-Devs
# Installiert CUPS, CUPS-PDF, Python-Build-Deps und legt Test-Queues an.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

echo "==> apt update / Basispakete"
apt-get update -y
apt-get install -y \
  cups \
  cups-client \
  cups-bsd \
  printer-driver-cups-pdf \
  python3 \
  python3-pip \
  python3-venv \
  python3-dev \
  build-essential \
  libcups2-dev \
  git \
  curl \
  ca-certificates

# CUPS-Dienst sicherstellen
systemctl enable --now cups.service

echo "==> CUPS: Admin-Rechte für vagrant (lpadmin)"
if id vagrant &>/dev/null; then
  usermod -aG lp,lpadmin vagrant
fi

echo "==> SPOCK2 Test-Queues (CUPS-PDF)"
# Idempotent: vorhandene Queues entfernen und neu anlegen
for q in spock-kitchen spock-counter spock-small; do
  lpadmin -x "$q" 2>/dev/null || true
  lpadmin -p "$q" -E -v cups-pdf:/ -m everywhere
  cupsenable "$q"
  cupsaccept "$q"
done

echo "==> Queue-Status"
lpstat -p -d || true
lpstat -v || true

echo "==> Hinweis: Repo unter /vagrant"
echo "    python3 -m venv /vagrant/.venv && source /vagrant/.venv/bin/activate"
echo "    pip install -e '/vagrant.[cups,dev]'"
echo "    cp /vagrant/config/spock2.example.toml ~/spock2.toml"
echo "    export SPOCK2_CONFIG=~/spock2.toml"
echo "==> Bootstrap fertig."
