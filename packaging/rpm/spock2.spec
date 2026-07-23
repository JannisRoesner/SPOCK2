# SPOCK2 — optionale RPM-Spec (Fedora/RHEL-Familie)
#
# Primärziel ist .deb (Ubuntu 24.04). Diese Spec ist ein grobes Skelett.
# Build (aus Repo-Root, nach %setup-Anpassung):
#   rpmbuild -ba packaging/rpm/spock2.spec
#
# Version mit pyproject.toml abstimmen.

Name:           spock2
Version:        0.1.0
Release:        1%{?dist}
Summary:        SPOCK2 kitchen kiosk client (RIKER/PICARD + CUPS)
License:        AGPL-3.0-or-later
URL:            https://github.com/JannisRoesner/SPOCK2
# Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch
# BuildArch noarch nur wenn reine Pure-Python; PySide6 oft arch-spezifisch → dann weglassen

BuildRequires:  python3-devel >= 3.12
BuildRequires:  python3-pip
BuildRequires:  python3-setuptools
BuildRequires:  python3-wheel
Requires:       python3 >= 3.12
Requires:       cups
Requires:       cups-client
Recommends:     cups-pdf

%description
Modularer PySide6-Kiosk-Client: RIKER-Bestellungen, optional PICARD,
Druck über CUPS-Queues spock-kitchen / spock-counter / spock-small.

%prep
# %setup -q
# Für In-Tree-Build: Source liegt im ausgecheckten Git-Repo.
# rpmbuild --define "_sourcedir …" anpassen oder tarball erzeugen.

%build
python3 -m pip wheel -w %{_builddir}/wheels .

%install
rm -rf %{buildroot}
python3 -m pip install --no-deps --root=%{buildroot} --prefix=/usr \
  %{_builddir}/wheels/spock2-*.whl

install -D -m 0644 config/spock2.example.toml \
  %{buildroot}%{_sysconfdir}/spock2/spock2.toml.example
install -D -m 0644 deploy/udev/99-spock-printers.rules \
  %{buildroot}%{_udevrulesdir}/99-spock-printers.rules
install -D -m 0644 deploy/systemd/spock2.service \
  %{buildroot}%{_unitdir}/spock2.service
install -D -m 0644 deploy/systemd/spock2.user.service \
  %{buildroot}%{_userunitdir}/spock2.service
install -D -m 0755 deploy/kiosk/spock2-session.sh \
  %{buildroot}%{_datadir}/spock2/kiosk/spock2-session.sh
install -D -m 0644 deploy/kiosk/spock2.desktop \
  %{buildroot}%{_datadir}/spock2/kiosk/spock2.desktop
install -D -m 0644 deploy/kiosk/spock2.desktop \
  %{buildroot}%{_datadir}/applications/spock2.desktop
install -D -m 0644 src/spock2/ui/resources/spock2_icon_256.png \
  %{buildroot}%{_datadir}/pixmaps/spock2.png
install -D -m 0644 src/spock2/ui/resources/spock2_icon_256.png \
  %{buildroot}%{_datadir}/icons/hicolor/256x256/apps/spock2.png

%files
%license LICENSE
%doc README.md deploy/cups/README.md
%config(noreplace) %{_sysconfdir}/spock2/spock2.toml.example
%{_bindir}/spock2
%{_bindir}/spock2-probe-usb
%{_bindir}/spock2-test-print
%{python3_sitelib}/spock2*
%{_udevrulesdir}/99-spock-printers.rules
%{_unitdir}/spock2.service
%{_userunitdir}/spock2.service
%{_datadir}/spock2/
%{_datadir}/applications/spock2.desktop
%{_datadir}/pixmaps/spock2.png
%{_datadir}/icons/hicolor/256x256/apps/spock2.png

%changelog
* Thu Jul 23 2026 SPOCK2 Contributors <spock2@localhost> - 0.1.0-1
- Initial optional RPM packaging skeleton
