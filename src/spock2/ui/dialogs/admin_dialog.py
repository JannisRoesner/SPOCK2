"""Admin-Dialog: editierbare Einstellungen und Testprint-Hooks."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
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


class AdminDialog(QDialog):
    """Editierbare Config (APIs, Polling, Druck, Drucker) inkl. Testprints."""

    def __init__(
        self,
        config: AppConfig,
        *,
        on_test_print: TestPrintCallback | None = None,
        on_apply: SettingsApplyCallback | None = None,
        list_queues: ListQueuesCallback | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Einstellungen")
        self.setModal(True)
        self._working = config.model_copy(deep=True)
        self._on_test_print = on_test_print
        self._on_apply = on_apply
        self._list_queues = list_queues
        self._discovered_queues: list[str] = []
        self._result_config: AppConfig | None = None

        touch = max(44, self._working.ui.min_touch_target_px)
        if parent is not None and parent.isVisible():
            geo = parent.geometry()
            self.resize(max(720, int(geo.width() * 0.72)), max(560, int(geo.height() * 0.78)))
        else:
            self.setMinimumSize(720, 560)
            self.resize(900, 700)
        self.setMinimumSize(640, 480)
        layout = QVBoxLayout(self)
        title = QLabel("SPOCK2 – Einstellungen")
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_api_tab(), "APIs")
        tabs.addTab(self._build_polling_tab(), "Polling")
        tabs.addTab(self._build_print_tab(), "Druck")
        tabs.addTab(self._build_printers_tab(), "Drucker")
        tabs.addTab(self._build_appearance_tab(), "Darstellung")
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
            save_btn.setMinimumHeight(touch)
            save_btn.setObjectName("primaryButton")
        if apply_btn is not None:
            apply_btn.setText("Übernehmen")
            apply_btn.setMinimumHeight(touch)
        if cancel_btn is not None:
            cancel_btn.setText("Abbrechen")
            cancel_btn.setMinimumHeight(touch)
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._on_apply_clicked)
        layout.addWidget(buttons)

    @property
    def result_config(self) -> AppConfig | None:
        return self._result_config

    def _build_api_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._riker_url = QLineEdit(self._working.riker.base_url)
        self._riker_url.setMinimumHeight(44)
        form.addRow("RIKER API Base URL", self._riker_url)

        self._picard_enabled = QCheckBox("PICARD aktiv")
        self._picard_enabled.setChecked(self._working.picard.enabled)
        self._picard_enabled.setMinimumHeight(44)
        form.addRow("", self._picard_enabled)

        self._picard_url = QLineEdit(self._working.picard.base_url)
        self._picard_url.setMinimumHeight(44)
        form.addRow("PICARD API Base URL", self._picard_url)
        return page

    def _build_polling_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._riker_interval = QDoubleSpinBox()
        self._riker_interval.setRange(0.5, 120.0)
        self._riker_interval.setSingleStep(0.5)
        self._riker_interval.setDecimals(1)
        self._riker_interval.setSuffix(" s")
        self._riker_interval.setValue(self._working.polling.riker_interval_s)
        self._riker_interval.setMinimumHeight(44)
        form.addRow("Polling-Intervall RIKER", self._riker_interval)

        self._picard_interval = QDoubleSpinBox()
        self._picard_interval.setRange(0.5, 120.0)
        self._picard_interval.setSingleStep(0.5)
        self._picard_interval.setDecimals(1)
        self._picard_interval.setSuffix(" s")
        self._picard_interval.setValue(self._working.polling.picard_interval_s)
        self._picard_interval.setMinimumHeight(44)
        form.addRow("Polling-Intervall PICARD", self._picard_interval)
        return page

    def _build_print_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self._auto_orders = QCheckBox("Neue Bestellungen automatisch drucken")
        self._auto_orders.setChecked(self._working.print.auto_print_new_orders)
        self._auto_orders.setMinimumHeight(48)
        layout.addWidget(self._auto_orders)

        self._auto_notes = QCheckBox("Neue PICARD-Zettel automatisch drucken")
        self._auto_notes.setChecked(self._working.print.auto_print_new_notes)
        self._auto_notes.setMinimumHeight(48)
        layout.addWidget(self._auto_notes)

        self._auto_complete = QCheckBox(
            "Bestellung nach erfolgreichem Druck als erledigt markieren"
        )
        self._auto_complete.setChecked(self._working.print.auto_complete_after_print)
        self._auto_complete.setMinimumHeight(48)
        layout.addWidget(self._auto_complete)

        hint = QLabel(
            "Hinweis: Auto-Complete ist optional und standardmäßig aus "
            "(Druck ≠ Erledigt)."
        )
        hint.setWordWrap(True)
        hint.setObjectName("adminHint")
        layout.addWidget(hint)
        layout.addStretch(1)
        return page

    def _build_printers_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        transport_row = QHBoxLayout()
        transport_row.setSpacing(12)
        transport_row.addWidget(QLabel("Druck-Transport"))
        self._transport = QComboBox()
        self._transport.setMinimumHeight(44)
        for key, label in _TRANSPORT_LABELS.items():
            self._transport.addItem(label, key)
        idx = self._transport.findData(self._working.print.transport)
        self._transport.setCurrentIndex(max(0, idx))
        self._transport.currentIndexChanged.connect(self._on_transport_changed)
        transport_row.addWidget(self._transport, stretch=1)
        refresh_btn = QPushButton("Drucker aktualisieren")
        refresh_btn.setObjectName("secondaryButton")
        refresh_btn.setMinimumHeight(44)
        refresh_btn.clicked.connect(self._refresh_queue_combos)
        transport_row.addWidget(refresh_btn)
        layout.addLayout(transport_row)

        self._queue_status = QLabel("")
        self._queue_status.setWordWrap(True)
        self._queue_status.setObjectName("adminHint")
        layout.addWidget(self._queue_status)

        self._printer_widgets: dict[PrinterRoleName, dict[str, object]] = {}
        profile_names = sorted(self._working.profiles.keys()) or ["tsp100", "pos5890k"]

        for role in ("kitchen", "counter", "small"):
            role_t: PrinterRoleName = role  # type: ignore[assignment]
            printer = self._printer_for_role(role_t)
            box = QGroupBox(_ROLE_LABELS[role_t])
            form = QFormLayout(box)
            form.setContentsMargins(12, 16, 12, 12)
            form.setHorizontalSpacing(16)
            form.setVerticalSpacing(10)

            enabled = QCheckBox("Aktiv")
            enabled.setChecked(printer.enabled if printer else True)
            enabled.setMinimumHeight(40)
            form.addRow("", enabled)

            queue = QComboBox()
            queue.setEditable(True)
            queue.setMinimumHeight(40)
            queue.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            current_queue = printer.queue if printer else f"spock-{role}"
            queue.currentTextChanged.connect(self._update_queue_warnings)
            form.addRow("Drucker / Queue", queue)

            warn = QLabel("")
            warn.setWordWrap(True)
            warn.setObjectName("fieldWarn")
            form.addRow("", warn)

            profile = QComboBox()
            profile.setMinimumHeight(40)
            for name in profile_names:
                profile.addItem(name)
            current_profile = printer.profile if printer else profile_names[0]
            pidx = profile.findText(current_profile)
            profile.setCurrentIndex(max(0, pidx))
            form.addRow("Profil", profile)

            layout.addWidget(box)
            self._printer_widgets[role_t] = {
                "enabled": enabled,
                "queue": queue,
                "queue_warn": warn,
                "profile": profile,
                "key": self._key_for_printer(printer) if printer else role,
                "initial_queue": current_queue,
            }

        hint = QLabel(
            "Tipp: Dieselbe Queue für Küche, Theke und Klein = Ein-Drucker-Betrieb. "
            "Ein Wechsel des Druck-Transports erfordert einen Neustart der App."
        )
        hint.setWordWrap(True)
        hint.setObjectName("adminHint")
        layout.addWidget(hint)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        for role in ("kitchen", "counter", "small"):
            btn = QPushButton(f"Test {_ROLE_LABELS[role]}")  # type: ignore[index]
            btn.setObjectName("secondaryButton")
            btn.setMinimumHeight(48)
            btn.clicked.connect(lambda _checked=False, r=role: self._test_print(r))
            btn_row.addWidget(btn)
        layout.addLayout(btn_row)
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
                        f"{len(queues)} System-Drucker/Queues gefunden ({mode})."
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
                warn.setText("Drucker nicht in Systemliste – Name prüfen.")
            else:
                warn.setText("")

    def _build_appearance_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        touch = max(44, self._working.ui.min_touch_target_px)

        self._theme = QComboBox()
        self._theme.setMinimumHeight(touch)
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
        self._ui_scale.setMinimumHeight(touch)
        form.addRow("UI-Skalierung", self._ui_scale)

        self._scale_with_window = QCheckBox("Mit Fenstergröße skalieren")
        self._scale_with_window.setChecked(self._working.ui.scale_with_window)
        self._scale_with_window.setMinimumHeight(touch)
        form.addRow("", self._scale_with_window)

        self._touch_target = QDoubleSpinBox()
        self._touch_target.setRange(32, 96)
        self._touch_target.setDecimals(0)
        self._touch_target.setSuffix(" px")
        self._touch_target.setValue(self._working.ui.min_touch_target_px)
        self._touch_target.setMinimumHeight(touch)
        form.addRow("Min. Touch-Höhe", self._touch_target)

        hint = QLabel(
            "Light/Dark gilt sofort nach Übernehmen. Die Skalierung passt Schriften "
            "und Touch-Flächen an Bildschirm bzw. Fenstergröße an (Basis 1280×800)."
        )
        hint.setWordWrap(True)
        hint.setObjectName("adminHint")
        form.addRow(hint)
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
        QMessageBox.information(self, "Testprint", f"Testprint für „{role}“ enqueued.")

    @classmethod
    def open_admin(
        cls,
        config: AppConfig,
        *,
        on_test_print: TestPrintCallback | None = None,
        on_apply: SettingsApplyCallback | None = None,
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
            list_queues=list_queues,
            parent=parent,
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.result_config
        return None
