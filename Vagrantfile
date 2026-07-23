# -*- mode: ruby -*-
# vi: set ft=ruby
#
# SPOCK2 Dev-VM für Windows-Entwickler: Ubuntu 24.04 + CUPS + CUPS-PDF.
# Nutzung (im Repo-Root, VirtualBox + Vagrant installiert):
#   vagrant up
#   vagrant ssh
#
# Freigegebenes Repo: /vagrant
# Bootstrap: deploy/vagrant/bootstrap.sh

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/noble64"
  config.vm.hostname = "spock2-dev"

  # Optional: feste IP für Host-Zugriff auf Dienste in der VM
  # config.vm.network "private_network", ip: "192.168.56.24"

  config.vm.provider "virtualbox" do |vb|
    vb.name = "SPOCK2-Ubuntu2404"
    vb.memory = 4096
    vb.cpus = 2
    # USB-Passthrough für Thermodrucker bei Bedarf im VirtualBox-UI aktivieren
  end

  # Hyper-V (Windows): Box ggf. anpassen, z. B. "generic/ubuntu2404"
  config.vm.provider "hyperv" do |hv|
    hv.vmname = "SPOCK2-Ubuntu2404"
    hv.memory = 4096
    hv.cpus = 2
  end

  config.vm.synced_folder ".", "/vagrant"

  config.vm.provision "shell", path: "deploy/vagrant/bootstrap.sh", privileged: true
end
