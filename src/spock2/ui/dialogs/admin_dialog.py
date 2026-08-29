"""Admin-Dialog: editierbare Einstellungen und Testprint-Hooks."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from spock2.config.models import (
    AppConfig,
    PrinterConfig,
    PrinterRoleName,
    PrintTransportMode,
    UiTheme,
)

TestPrintCallback = Callable[[str], None]
SettingsApplyCallback = Callable[[AppConfig], str | None]
ConnectionTestCallback = Callable[[AppConfig], str]
ListQueuesCallback = Callable[[PrintTransportMode], list[str]]

_ROLE_LABELS: dict[PrinterRoleName, str] = {
    "kitchen": "Küche",
    "counter": "Theke",
    "small": "Klein",
}

_TRANSPORT_LABELS: dict[PrintTransportMode, str] = {
    "auto": "Auto (Linux→CUPS, Windows→WinSpool, sonst Datei)",
    "cups": "CUPS",
    "winspool": "Windows-Spooler (RAW)",
    "file": "Virtuell / Datei (Test)",
}


def _form(page: QWidget) -> QFormLayout:
    """Formular-Layout, das lange Labels umbricht statt abzuschneiden."""
    form = QFormLayout(page)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    form.setFormAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
    form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(8)
    form.setContentsMargins(4, 4, 4, 4)
    return form


def _hint(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("adminHint")
    label.setWordWrap(True)
    return label


class AdminDialog(QDialog):
    """Editierbare Config (APIs, Polling, Druck, Drucker) inkl. Testprints."""

    def __init__(
        self,
        config: AppConfig,
        *,
        on_test_print: TestPrintCallback | None = None,
        on_apply: SettingsApplyCallback | None = None,
        on_connection_test: ConnectionTestCallback | None = None,
        list_queues: ListQueuesCallback | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        self._working = config.model_copy(deep=True)
        self._on_test_print = on_test_print
        self._on_apply = on_apply
        self._on_connection_test = on_connection_test
        self._list_queues = list_queues
        self._discovered_queues: list[str] = []
        self._result_config: AppConfig | None = None

        self._apply_dialog_geometry(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title = QLabel("SPOCK2 – Einstellungen")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        # Fünf kurze Reiter passen immer; Scroll-Pfeile würden nur Platz kosten.
        tabs.setUsesScrollButtons(False)
        tabs.tabBar().setExpanding(False)
        tabs.tabBar().setElideMode(Qt.TextElideMode.ElideRight)
        tabs.addTab(self._scrollable(self._build_api_tab()), "APIs")
        tabs.addTab(self._scrollable(self._build_polling_tab()), "Polling")
        tabs.addTab(self._scrollable(self._build_print_tab()), "Druck")
        tabs.addTab(self._scrollable(self._build_printers_tab()), "Drucker")
        tabs.addTab(self._scrollable(self._build_appearance_tab()), "Darstellung")
        layout.addWidget(tabs, stretch=1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        save_btn = buttons.button(QDialogButtonBox.StandardButton.Save)
        apply_btn = buttons.button(QDialogButtonBox.StandardButton.Apply)
        cancel_btn = buttons.button(QDialogButtonBox.StandardButton.Cancel)
        if save_btn is not None:
            save_btn.setText("Speichern")
            save_btn.setObjectName("primaryButton")
        if apply_btn is not None:
            apply_btn.setText("Übernehmen")
            apply_btn.clicked.connect(self._on_apply_clicked)
        if cancel_btn is not None:
            cancel_btn.setText("Abbrechen")
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _apply_dialog_geometry(self, parent: QWidget | None) -> None:
        """Passt den Dialog an den Bildschirm an (nie größer als sichtbar)."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen is not None else None
        max_w, max_h = (1024, 768)
        if available is not None:
            max_w = max(480, int(available.width() * 0.92))
            max_h = max(400, int(available.height() * 0.92))
        width, height = min(940, max_w), min(720, max_h)
        if parent is not None and parent.isVisible():
            geo = parent.geometry()
            width = min(max(720, int(geo.width() * 0.8)), max_w)
            height = min(max(560, int(geo.height() * 0.85)), max_h)
        self.setMinimumSize(min(520, width), min(420, height))
        self.resize(width, height)

    @staticmethod
    def _scrollable(page: QWidget) -> QWidget:
        """Tab-Inhalte scrollbar machen – sonst überlappen sie auf kleinen Displays."""
        area = QScrollArea()
        area.setWidgetResizable(True)
        area.setFrameShape(QScrollArea.Shape.NoFrame)
        area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        page.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        area.setWidget(page)
        return area

    @property
    def result_config(self) -> AppConfig | None:
        return self._result_config

    def _build_api_tab(self) -> QWidget:
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.setContentsMargins(4, 4, 4, 4)
        outer.setSpacing(10)

        endpoints = QGroupBox("Endpunkte")
        form = _form(endpoints)

        self._riker_url = QLineEdit(self._working.riker.base_url)
        self._riker_url.setPlaceholderText("https://riker.example.de")
        form.addRow("RIKER API Base URL", self._riker_url)

        self._picard_enabled = QCheckBox("PICARD aktiv")
        self._picard_enabled.setChecked(self._working.picard.enabled)
        form.addRow("", self._picard_enabled)

        self._picard_url = QLineEdit(self._working.picard.base_url)
        self._picard_url.setPlaceholderText("https://picard.example.de")
        form.addRow("PICARD API Base URL", self._picard_url)
        outer.addWidget(endpoints)

        tls = QGroupBox("TLS / Zertifikate")
        tls_form = _form(tls)
        self._ssl_verify = QCheckBox("Server-Zertifikat prüfen")
        self._ssl_verify.setChecked(self._working.tls.ssl_verify)
        tls_form.addRow("", self._ssl_verify)

        ca_row = QWidget()
        ca_layout = QHBoxLayout(ca_row)
        ca_layout.setContentsMargins(0, 0, 0, 0)
        ca_layout.setSpacing(8)
        self._ca_bundle = QLineEdit(self._working.tls.ca_bundle)
        self._ca_bundle.setPlaceholderText("leer = System-Zertifikate")
        ca_layout.addWidget(self._ca_bundle, stretch=1)
        browse = QPushButton("…")
        browse.setObjectName("secondaryButton")
        browse.setMaximumWidth(64)
        browse.clicked.connect(self._pick_ca_bundle)
        ca_layout.addWidget(browse)
        tls_form.addRow("CA-Bundle (PEM)", ca_row)

        tls_form.addRow(
            _hint(
                "Selbst ausgestellte Zertifikate: entweder das CA-Bundle (PEM) "
                "hinterlegen oder die Prüfung abschalten. Ohne Prüfung ist die "
                "Verbindung verschlüsselt, aber nicht gegen Fälschung geschützt."
            )
        )
        outer.addWidget(tls)

        test_row = QHBoxLayout()
        test_row.setSpacing(8)
        self._test_conn_btn = QPushButton("Verbindung testen")
        self._test_conn_btn.setObjectName("secondaryButton")
        self._test_conn_btn.clicked.connect(self._test_connection)
        test_row.addWidget(self._test_conn_btn)
        test_row.addStretch(1)
        outer.addLayout(test_row)

        self._conn_result = _hint("")
        outer.addWidget(self._conn_result)
        outer.addStretch(1)
        return page

    def _pick_ca_bundle(self) -> None:
        path, _filter = QFileDialog.getOpenFileName(
            self,
            "CA-Bundle wählen",
            self._ca_bundle.text() or "/etc/ssl/certs",
            "Zertifikate (*.pem *.crt *.cer);;Alle Dateien (*)",
        )
        if path:
            self._ca_bundle.setText(path)

    def _test_connection(self) -> None:
        if self._on_connection_test is None:
            self._conn_result.setText("Kein Verbindungstest verdrahtet.")
            return
        cfg = self._collect()
        if cfg is None:
            return
        self._conn_result.setText("Teste Verbindung…")
        self._test_conn_btn.setEnabled(False)
        QGuiApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        # Der Test blockiert den Event-Loop; ohne repaint bleibt der Dialog leer.
        self._conn_result.repaint()
        try:
            report = self._on_connection_test(cfg)
        except Exception as exc:  # noqa: BLE001 – Ergebnis gehört in den Dialog
            report = f"Test fehlgeschlagen: {exc}"
        finally:
            QGuiApplication.restoreOverrideCursor()
            self._test_conn_btn.setEnabled(True)
        self._conn_result.setText(report)

    def _build_polling_tab(self) -> QWidget:
        page = QWidget()
        form = _form(page)

        self._riker_interval = QDoubleSpinBox()
        self._riker_interval.setRange(0.5, 120.0)
        self._riker_interval.setSingleStep(0.5)
        self._riker_interval.setDecimals(1)
        self._riker_interval.setSuffix(" s")
        self._riker_interval.setValue(self._working.polling.riker_interval_s)
        form.addRow("Polling-Intervall RIKER", self._riker_interval)

        self._picard_interval = QDoubleSpinBox()
        self._picard_interval.setRange(0.5, 120.0)
        self._picard_interval.setSingleStep(0.5)
        self._picard_interval.setDecimals(1)
        self._picard_interval.setSuffix(" s")
        self._picard_interval.setValue(self._working.polling.picard_interval_s)
        form.addRow("Polling-Intervall PICARD", self._picard_interval)
        form.addRow(
            _hint(
                "Kürzere Intervalle bedeuten mehr Last auf RIKER/PICARD. "
                "3 Sekunden sind für den Küchenbetrieb üblich."
            )
        )
        return page

    def _build_print_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)

        self._auto_orders = QCheckBox("Neue Bestellungen automatisch drucken")
        self._auto_orders.setChecked(self._working.print.auto_print_new_orders)
        layout.addWidget(self._auto_orders)

        self._auto_notes = QCheckBox("Neue PICARD-Zettel automatisch drucken")
        self._auto_notes.setChecked(self._working.print.auto_print_new_notes)
        layout.addWidget(self._auto_notes)

        self._auto_complete = QCheckBox(
            "Bestellung nach erfolgreichem Druck als erledigt markieren"
        )
        self._auto_complete.setChecked(self._working.print.auto_complete_after_print)
        layout.addWidget(self._auto_complete)

        layout.addWidget(
            _hint(
                "Hinweis: Auto-Complete ist optional und standardmäßig aus "
                "(Druck ≠ Erledigt)."
            )
        )
        layout.addStretch(1)
        return page

    def _build_printers_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)

        transport_box = QGroupBox("Druck-Transport")
        transport_grid = QGridLayout(transport_box)
        transport_grid.setContentsMargins(12, 12, 12, 12)
        transport_grid.setHorizontalSpacing(12)
        transport_grid.setVerticalSpacing(8)
        self._transport = QComboBox()
        for key, label in _TRANSPORT_LABELS.items():
            self._transport.addItem(label, key)
        idx = self._transport.findData(self._working.print.transport)
        self._transport.setCurrentIndex(max(0, idx))
        self._transport.currentIndexChanged.connect(self._on_transport_changed)
        transport_grid.addWidget(self._transport, 0, 0)
        refresh_btn = QPushButton("Drucker aktualisieren")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.clicked.connect(self._refresh_queue_combos)
        # Eigene Zeile: nebeneinander wurde der Button auf kleinen Displays
        # bis zur Unlesbarkeit beschnitten.
        transport_grid.addWidget(refresh_btn, 1, 0, Qt.AlignmentFlag.AlignLeft)
        self._queue_status = _hint("")
        transport_grid.addWidget(self._queue_status, 2, 0)
        transport_grid.setColumnStretch(0, 1)
        layout.addWidget(transport_box)

        self._printer_widgets: dict[PrinterRoleName, dict[str, object]] = {}
        profile_names = sorted(self._working.profiles.keys()) or ["tsp100", "pos5890k"]

        for role in ("kitchen", "counter", "small"):
            role_t: PrinterRoleName = role  # type: ignore[assignment]
            printer = self._printer_for_role(role_t)
            box = QGroupBox(_ROLE_LABELS[role_t])
            form = _form(box)
            form.setContentsMargins(12, 12, 12, 12)

            enabled = QCheckBox("Aktiv")
            enabled.setChecked(printer.enabled if printer else True)
            form.addRow("", enabled)

            queue = QComboBox()
            queue.setEditable(True)
            queue.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            queue.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            queue.setMinimumContentsLength(12)
            current_queue = printer.queue if printer else f"spock-{role}"
            queue.currentTextChanged.connect(self._update_queue_warnings)
            form.addRow("Drucker / Queue", queue)

            warn = QLabel("")
            warn.setWordWrap(True)
            warn.setObjectName("fieldWarn")
            form.addRow("", warn)

            profile = QComboBox()
            for name in profile_names:
                profile.addItem(name)
            current_profile = printer.profile if printer else profile_names[0]
            pidx = profile.findText(current_profile)
            profile.setCurrentIndex(max(0, pidx))
            form.addRow("Profil", profile)

            test_btn = QPushButton(f"Test {_ROLE_LABELS[role_t]}")
            test_btn.setObjectName("secondaryButton")
            test_btn.clicked.connect(lambda _checked=False, r=role: self._test_print(r))
            form.addRow("", test_btn)

            layout.addWidget(box)
            self._printer_widgets[role_t] = {
                "enabled": enabled,
                "queue": queue,
                "queue_warn": warn,
                "profile": profile,
                "key": self._key_for_printer(printer) if printer else role,
                "initial_queue": current_queue,
            }

        layout.addWidget(
            _hint(
                "Tipp: Dieselbe Queue für Küche, Theke und Klein = Ein-Drucker-Betrieb. "
                "Ein Wechsel des Druck-Transports erfordert einen Neustart der App."
            )
        )
        layout.addStretch(1)
        self._refresh_queue_combos()
        return page

    def _selected_transport_mode(self) -> PrintTransportMode:
        data = self._transport.currentData()
        if data in ("auto", "cups", "winspool", "file"):
            return data  # type: ignore[return-value]
        return "auto"

    def _on_transport_changed(self, _index: int = 0) -> None:
        self._refresh_queue_combos()

    def _refresh_queue_combos(self) -> None:
        mode = self._selected_transport_mode()
        queues: list[str] = []
        if self._list_queues is not None:
            try:
                queues = list(self._list_queues(mode) or [])
            except Exception as exc:  # noqa: BLE001
                self._queue_status.setText(f"Druckerliste nicht lesbar: {exc}")
                queues = []
            else:
                if queues:
                    self._queue_status.setText(
                        f"{len(queues)} System-Drucker/Queues gefunden ({mode}): "
                        + ", ".join(queues)
                    )
                else:
                    self._queue_status.setText(
                        "Keine System-Drucker gefunden – Name manuell eingeben oder "
                        "„Drucker aktualisieren“."
                    )
        else:
            self._queue_status.setText(
                "Keine Drucker-Discovery verdrahtet – Queue manuell eingeben."
            )

        self._discovered_queues = queues
        for role, widgets in self._printer_widgets.items():
            combo = widgets["queue"]
            assert isinstance(combo, QComboBox)
            current = combo.currentText().strip()
            if not current:
                initial = widgets.get("initial_queue")
                current = str(initial) if initial else f"spock-{role}"
            combo.blockSignals(True)
            combo.clear()
            items = list(queues)
            if current and current not in items:
                items = [current, *items]
            combo.addItems(items)
            combo.setCurrentText(current)
            combo.blockSignals(False)
        self._update_queue_warnings()

    def _update_queue_warnings(self, _text: str = "") -> None:
        discovered = set(self._discovered_queues)
        for widgets in self._printer_widgets.values():
            combo = widgets["queue"]
            warn = widgets["queue_warn"]
            assert isinstance(combo, QComboBox)
            assert isinstance(warn, QLabel)
            name = combo.currentText().strip()
            if not name:
                warn.setText("Kein Drucker gewählt.")
            elif discovered and name not in discovered:
                warn.setText(
                    "Drucker nicht in Systemliste – so schlägt jeder Druck fehl."
                )
            else:
                warn.setText("")

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        form = _form(page)

        self._theme = QComboBox()
        themes: list[tuple[UiTheme, str]] = [
            ("light", "Light-Design"),
            ("dark", "Dark-Design"),
        ]
        for key, label in themes:
            self._theme.addItem(label, key)
        tidx = self._theme.findData(self._working.ui.theme)
        self._theme.setCurrentIndex(max(0, tidx))
        form.addRow("Farbschema", self._theme)

        self._ui_scale = QDoubleSpinBox()
        self._ui_scale.setRange(0.75, 1.75)
        self._ui_scale.setSingleStep(0.05)
        self._ui_scale.setDecimals(2)
        self._ui_scale.setSuffix(" ×")
        self._ui_scale.setValue(self._working.ui.ui_scale)
        form.addRow("UI-Skalierung", self._ui_scale)

        self._scale_with_window = QCheckBox("Mit Fenstergröße skalieren")
        self._scale_with_window.setChecked(self._working.ui.scale_with_window)
        form.addRow("", self._scale_with_window)

        self._touch_target = QDoubleSpinBox()
        self._touch_target.setRange(32, 96)
        self._touch_target.setDecimals(0)
        self._touch_target.setSuffix(" px")
        self._touch_target.setValue(self._working.ui.min_touch_target_px)
        form.addRow("Min. Touch-Höhe", self._touch_target)

        self._fullscreen = QCheckBox("Vollbild beim Start")
        self._fullscreen.setChecked(self._working.ui.fullscreen)
        form.addRow("", self._fullscreen)

        self._confirm_complete = QCheckBox("„Erledigt“ bestätigen lassen")
        self._confirm_complete.setChecked(self._working.ui.confirm_complete)
        form.addRow("", self._confirm_complete)

        form.addRow(
            _hint(
                "Light/Dark gilt sofort nach Übernehmen. Die Skalierung passt Schriften "
                "und Touch-Flächen an Bildschirm bzw. Fenstergröße an (Basis 1280×800)."
            )
        )
        return page

    def _printer_for_role(self, role: PrinterRoleName) -> PrinterConfig | None:
        for printer in self._working.printers.values():
            if printer.role == role:
                return printer
        return None

    def _key_for_printer(self, target: PrinterConfig) -> str:
        for name, printer in self._working.printers.items():
            if printer is target or (
                printer.role == target.role and printer.queue == target.queue
            ):
                return name
        return target.role

    def _collect(self) -> AppConfig | None:
        url = self._riker_url.text().strip()
        if not url:
            QMessageBox.warning(self, "Einstellungen", "RIKER Base URL darf nicht leer sein.")
            return None
        picard_url = self._picard_url.text().strip()
        if self._picard_enabled.isChecked() and not picard_url:
            QMessageBox.warning(self, "Einstellungen", "PICARD Base URL darf nicht leer sein.")
            return None

        cfg = self._working.model_copy(deep=True)
        cfg.riker.base_url = url
        cfg.picard.enabled = self._picard_enabled.isChecked()
        cfg.picard.base_url = picard_url or cfg.picard.base_url
        cfg.tls.ssl_verify = self._ssl_verify.isChecked()
        cfg.tls.ca_bundle = self._ca_bundle.text().strip()
        cfg.polling.riker_interval_s = float(self._riker_interval.value())
        cfg.polling.picard_interval_s = float(self._picard_interval.value())
        cfg.polling.interval_s = cfg.polling.riker_interval_s
        cfg.print.auto_print_new_orders = self._auto_orders.isChecked()
        cfg.print.auto_print_new_notes = self._auto_notes.isChecked()
        cfg.print.auto_complete_after_print = self._auto_complete.isChecked()
        transport = self._transport.currentData()
        if transport in ("auto", "cups", "winspool", "file"):
            cfg.print.transport = transport  # type: ignore[assignment]

        new_printers: dict[str, PrinterConfig] = {}
        for role, widgets in self._printer_widgets.items():
            key = str(widgets["key"])
            queue_combo = widgets["queue"]
            profile_combo = widgets["profile"]
            enabled_box = widgets["enabled"]
            assert isinstance(queue_combo, QComboBox)
            assert isinstance(profile_combo, QComboBox)
            assert isinstance(enabled_box, QCheckBox)
            queue = queue_combo.currentText().strip() or f"spock-{role}"
            profile = profile_combo.currentText().strip() or "tsp100"
            new_printers[key] = PrinterConfig(
                role=role,
                queue=queue,
                profile=profile,
                enabled=enabled_box.isChecked(),
            )
        # Behalte ggf. weitere Drucker-Einträge mit anderen Rollen nicht — V1 nur 3 Rollen.
        cfg.printers = new_printers

        theme = self._theme.currentData()
        if theme in ("light", "dark"):
            cfg.ui.theme = theme  # type: ignore[assignment]
        cfg.ui.ui_scale = float(self._ui_scale.value())
        cfg.ui.scale_with_window = self._scale_with_window.isChecked()
        cfg.ui.min_touch_target_px = int(self._touch_target.value())
        cfg.ui.fullscreen = self._fullscreen.isChecked()
        cfg.ui.confirm_complete = self._confirm_complete.isChecked()

        self._working = cfg
        return cfg

    def _apply_collected(self, *, close_on_success: bool) -> bool:
        cfg = self._collect()
        if cfg is None:
            return False
        if self._on_apply is None:
            self._result_config = cfg
            if close_on_success:
                self.accept()
            return True
        message = self._on_apply(cfg)
        self._result_config = cfg
        if message:
            QMessageBox.information(self, "Einstellungen", message)
        if close_on_success:
            self.accept()
        return True

    def _on_save(self) -> None:
        self._apply_collected(close_on_success=True)

    def _on_apply_clicked(self) -> None:
        self._apply_collected(close_on_success=False)

    def _test_print(self, role: str) -> None:
        if self._on_test_print is None:
            QMessageBox.information(
                self,
                "Testprint",
                f"Kein Testprint-Hook verdrahtet (Rolle: {role}).",
            )
            return
        if not self._apply_collected(close_on_success=False):
            return
        try:
            self._on_test_print(role)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Testprint fehlgeschlagen", str(exc))
            return
        queue = ""
        widgets = self._printer_widgets.get(role)  # type: ignore[arg-type]
        if widgets is not None:
            combo = widgets["queue"]
            if isinstance(combo, QComboBox):
                queue = combo.currentText().strip()
        target = f" → Queue „{queue}“" if queue else ""
        QMessageBox.information(
            self,
            "Testprint",
            f"Testprint für „{role}“{target} eingereiht.\n"
            "Kommt nichts aus dem Drucker, zeigt die Statusleiste den Fehler.",
        )

    @classmethod
    def open_admin(
        cls,
        config: AppConfig,
        *,
        on_test_print: TestPrintCallback | None = None,
        on_apply: SettingsApplyCallback | None = None,
        on_connection_test: ConnectionTestCallback | None = None,
        list_queues: ListQueuesCallback | None = None,
        parent: QWidget | None = None,
        admin_pin: str = "",
    ) -> AppConfig | None:
        if admin_pin:
            text, ok = QInputDialog.getText(
                parent,
                "Admin-PIN",
                "PIN eingeben:",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return None
            if text != admin_pin:
                QMessageBox.warning(parent, "Admin", "Falscher PIN.")
                return None
        dlg = cls(
            config,
            on_test_print=on_test_print,
            on_apply=on_apply,
            on_connection_test=on_connection_test,
            list_queues=list_queues,
            parent=parent,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.result_config
        return None
