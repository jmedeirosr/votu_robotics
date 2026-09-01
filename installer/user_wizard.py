#!/usr/bin/env python3
"""Graphical per-user installer and uninstaller for Votu FieldOps."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QIcon, QPalette, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)


APP_NAME = "Votu FieldOps"
APP_ID = "votu-fieldops"
VERSION = "1.0.0"
HOME = Path.home()
DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", HOME / ".local" / "share"))
DEFAULT_TARGET = DATA_HOME / APP_ID
BIN_DIR = HOME / ".local" / "bin"
MENU_DIR = DATA_HOME / "applications"
ICON_DIR = DATA_HOME / "icons" / "hicolor" / "256x256" / "apps"

STYLE = """
QWizard, QDialog { background: #f3f7f4; }
QWidget { color: #10231b; font-family: "Segoe UI", "Noto Sans"; font-size: 13px; }
QLabel { color: #10231b; background: transparent; }
QLabel#hero { color: #123f2f; font-size: 25px; font-weight: 700; }
QLabel#subtitle { color: #40584e; font-size: 13px; }
QLabel#card { background: #ffffff; color: #10231b; border: 1px solid #cbdcd2; border-radius: 12px; padding: 16px; }
QLineEdit, QPlainTextEdit {
    background: #ffffff; color: #0b1f17; border: 1px solid #9eb9aa;
    border-radius: 8px; padding: 8px; selection-background-color: #bce5ca;
    selection-color: #07150f;
}
QCheckBox { color: #10231b; spacing: 9px; padding: 4px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QProgressBar {
    min-height: 22px; border: 1px solid #9eb9aa; border-radius: 11px;
    background: #e1ebe5; color: #10231b; text-align: center; font-weight: 700;
}
QProgressBar::chunk { border-radius: 10px; background: #3eaf76; }
QPushButton {
    min-width: 96px; min-height: 36px; padding: 0 15px; border: 0;
    border-radius: 8px; background: #176b4d; color: white; font-weight: 700;
}
QPushButton:hover { background: #10543b; }
QPushButton:disabled { background: #c7d4cc; color: #64776d; }
"""


def asset_path(name: str, payload: Path | None, target: Path | None = None) -> Path:
    candidates = [root / name for root in (payload, target) if root is not None]
    return next((path for path in candidates if path.exists()), Path("/__missing_asset__"))


def heading(page: QWizardPage, title: str, subtitle: str, icon: Path) -> QVBoxLayout:
    layout = QVBoxLayout(page)
    layout.setContentsMargins(28, 24, 28, 24)
    layout.setSpacing(14)
    row = QHBoxLayout()
    if icon.exists():
        logo = QLabel()
        logo.setPixmap(
            QPixmap(str(icon)).scaled(
                230,
                72,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        )
        logo.setFixedSize(240, 78)
        row.addWidget(logo)
    texts = QVBoxLayout()
    label = QLabel(title)
    label.setObjectName("hero")
    sub = QLabel(subtitle)
    sub.setObjectName("subtitle")
    sub.setWordWrap(True)
    texts.addWidget(label)
    texts.addWidget(sub)
    row.addLayout(texts, 1)
    layout.addLayout(row)
    return layout


class WelcomePage(QWizardPage):
    def __init__(self, icon: Path, uninstall: bool = False):
        super().__init__()
        action = "desinstalação" if uninstall else "instalação"
        layout = heading(self, f"{APP_NAME} {VERSION}", f"Assistente profissional de {action}", icon)
        message = QLabel(
            "Este assistente removerá o Votu FieldOps e seus atalhos deste usuário."
            if uninstall
            else "O aplicativo será instalado somente para o usuário atual, sem solicitar senha administrativa."
        )
        message.setObjectName("card")
        message.setWordWrap(True)
        layout.addWidget(message)
        layout.addStretch(1)


class LicensePage(QWizardPage):
    def __init__(self, icon: Path, license_file: Path):
        super().__init__()
        layout = heading(self, "Termos de licença", "Leia e aceite os termos para continuar.", icon)
        text = QPlainTextEdit()
        text.setReadOnly(True)
        text.setPlainText(license_file.read_text(encoding="utf-8"))
        layout.addWidget(text, 1)
        accepted = QCheckBox("Aceito os termos da licença")
        layout.addWidget(accepted)
        self.registerField("licenseAccepted*", accepted)


class DirectoryPage(QWizardPage):
    def __init__(self, icon: Path):
        super().__init__()
        layout = heading(self, "Local da instalação", "Escolha onde os arquivos serão armazenados.", icon)
        row = QHBoxLayout()
        self.path = QLineEdit(str(DEFAULT_TARGET))
        browse = QPushButton("Procurar")
        browse.clicked.connect(self.choose)
        row.addWidget(self.path, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        info = QLabel("O diretório deve pertencer ao usuário atual. Nenhuma senha será solicitada.")
        info.setObjectName("subtitle")
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch(1)
        self.registerField("targetDir*", self.path)

    def choose(self):
        selected = QFileDialog.getExistingDirectory(self, "Selecionar diretório", str(self.path.text()))
        if selected:
            self.path.setText(str(Path(selected) / APP_ID))


class OptionsPage(QWizardPage):
    def __init__(self, icon: Path):
        super().__init__()
        layout = heading(self, "Opções", "Personalize os atalhos e a primeira execução.", icon)
        self.menu = QCheckBox("Criar entrada no menu de aplicativos")
        self.desktop = QCheckBox("Criar atalho na Área de Trabalho")
        self.run_after = QCheckBox("Executar o Votu FieldOps após instalar")
        self.menu.setChecked(True)
        self.desktop.setChecked(True)
        self.run_after.setChecked(False)
        for widget in (self.menu, self.desktop, self.run_after):
            layout.addWidget(widget)
        layout.addStretch(1)
        self.registerField("createMenu", self.menu)
        self.registerField("createDesktop", self.desktop)
        self.registerField("runAfter", self.run_after)


class SummaryPage(QWizardPage):
    def __init__(self, icon: Path):
        super().__init__()
        self.layout = heading(self, "Resumo", "Confirme os dados antes de instalar.", icon)
        self.summary = QLabel()
        self.summary.setObjectName("card")
        self.summary.setWordWrap(True)
        self.layout.addWidget(self.summary)
        self.layout.addStretch(1)

    def initializePage(self):
        wizard = self.wizard()
        options = []
        if wizard.field("createMenu"):
            options.append("Entrada no menu")
        if wizard.field("createDesktop"):
            options.append("Atalho na Área de Trabalho")
        if wizard.field("runAfter"):
            options.append("Executar ao concluir")
        self.summary.setText(
            f"Versão: {VERSION}\n"
            f"Arquitetura: Bullseye ARM64\n"
            f"Destino: {wizard.field('targetDir')}\n"
            f"Opções: {', '.join(options) or 'Nenhuma'}"
        )


class CopyWorker(QThread):
    progress = pyqtSignal(int, str)
    failed = pyqtSignal(str)
    completed = pyqtSignal()

    def __init__(self, payload: Path, target: Path, menu: bool, desktop: bool):
        super().__init__()
        self.payload = payload
        self.target = target
        self.menu = menu
        self.desktop = desktop

    def run(self):
        try:
            files = [path for path in self.payload.rglob("*") if path.is_file()]
            total = sum(path.stat().st_size for path in files) or 1
            copied = 0
            self.target.mkdir(parents=True, exist_ok=True)
            for source in files:
                relative = source.relative_to(self.payload)
                destination = self.target / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                copied += source.stat().st_size
                self.progress.emit(min(94, int(copied * 94 / total)), f"Copiando {relative.name}...")
            self.progress.emit(96, "Criando atalhos...")
            self.create_launchers()
            self.progress.emit(100, "Instalação concluída.")
            self.completed.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

    def create_launchers(self):
        BIN_DIR.mkdir(parents=True, exist_ok=True)
        MENU_DIR.mkdir(parents=True, exist_ok=True)
        ICON_DIR.mkdir(parents=True, exist_ok=True)
        launcher = BIN_DIR / APP_ID
        launcher.write_text(
            "#!/bin/sh\nexport PYTHONNOUSERSITE=1\nexport QT_AUTO_SCREEN_SCALE_FACTOR=1\n"
            f'exec "{self.target}/runtime/bin/python3" "{self.target}/app/src/interface.py" "$@"\n',
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        uninstall_launcher = BIN_DIR / f"{APP_ID}-uninstall"
        uninstall_launcher.write_text(
            "#!/bin/sh\n"
            f'exec "{self.target}/runtime/bin/python3" "{self.target}/installer_wizard.py" '
            f'--uninstall --target "{self.target}"\n',
            encoding="utf-8",
        )
        uninstall_launcher.chmod(0o755)
        desktop_entry = (
            "[Desktop Entry]\nType=Application\nName=Votu FieldOps\n"
            "Comment=Operação e transmissão de mapas de campo\n"
            # Freedesktop menus on Raspberry Pi OS do not reliably decode ICO
            # files and fall back to a generic application icon. PNG preserves
            # the same logo and is the native desktop-entry format.
            f"Exec={launcher}\nIcon={self.target}/logo-long-menu.png\n"
            "Terminal=false\nCategories=Utility;Science;\nStartupNotify=true\n"
        )
        uninstall_entry = (
            "[Desktop Entry]\nType=Application\nName=Desinstalar Votu FieldOps\n"
            f"Exec={uninstall_launcher}\nIcon={self.target}/uninstaller-icon.ico\n"
            "Terminal=false\nCategories=Utility;Settings;\n"
        )
        if self.menu:
            (MENU_DIR / f"{APP_ID}.desktop").write_text(desktop_entry, encoding="utf-8")
            (MENU_DIR / f"{APP_ID}-uninstall.desktop").write_text(uninstall_entry, encoding="utf-8")
        if self.desktop and (HOME / "Desktop").is_dir():
            shortcut = HOME / "Desktop" / "Votu FieldOps.desktop"
            shortcut.write_text(desktop_entry, encoding="utf-8")
            shortcut.chmod(0o755)
        manifest = {
            "version": VERSION,
            "target": str(self.target),
            "menu": self.menu,
            "desktop": self.desktop,
        }
        (self.target / "install-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        (DATA_HOME / f"{APP_ID}.location").write_text(str(self.target), encoding="utf-8")


class InstallPage(QWizardPage):
    def __init__(self, icon: Path, payload: Path):
        super().__init__()
        self.payload = payload
        self.done = False
        self.started = False
        layout = heading(self, "Instalando", "Aguarde enquanto o Votu FieldOps é configurado.", icon)
        self.status = QLabel("Preparando instalação...")
        self.progress = QProgressBar()
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addStretch(1)

    def initializePage(self):
        if self.started:
            return
        self.started = True
        wizard = self.wizard()
        self.worker = CopyWorker(
            self.payload,
            Path(str(wizard.field("targetDir"))).expanduser(),
            bool(wizard.field("createMenu")),
            bool(wizard.field("createDesktop")),
        )
        self.worker.progress.connect(self.update_progress)
        self.worker.failed.connect(self.on_error)
        self.worker.completed.connect(self.on_complete)
        self.worker.start()

    def update_progress(self, value: int, message: str):
        self.progress.setValue(value)
        self.status.setText(message)

    def on_complete(self):
        self.done = True
        self.completeChanged.emit()
        QTimer.singleShot(350, self.wizard().next)

    def on_error(self, message: str):
        self.status.setText("Falha na instalação.")
        QMessageBox.critical(self, APP_NAME, message)

    def isComplete(self):
        return self.done


class FinishPage(QWizardPage):
    def __init__(self, icon: Path, uninstall: bool = False):
        super().__init__()
        title = "Desinstalação concluída" if uninstall else "Instalação concluída"
        subtitle = "O Votu FieldOps foi removido." if uninstall else "O Votu FieldOps está pronto para uso."
        layout = heading(self, title, subtitle, icon)
        message = QLabel(
            "Você pode fechar este assistente."
            if uninstall
            else "Abra o aplicativo pelo menu ou pelo atalho criado na Área de Trabalho."
        )
        message.setObjectName("card")
        message.setWordWrap(True)
        layout.addWidget(message)
        layout.addStretch(1)


class InstallWizard(QWizard):
    def __init__(self, payload: Path):
        super().__init__()
        icon = asset_path("installer-icon.ico", payload)
        brand = asset_path("logo-long.png", payload)
        self.setWindowTitle(f"Instalar {APP_NAME}")
        self.setWindowIcon(QIcon(str(icon)))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(820, 560)
        self.setOption(QWizard.WizardOption.NoBackButtonOnStartPage)
        self.setOption(QWizard.WizardOption.NoBackButtonOnLastPage)
        self.addPage(WelcomePage(brand))
        self.addPage(LicensePage(brand, payload / "LICENSE.txt"))
        self.addPage(DirectoryPage(brand))
        self.addPage(OptionsPage(brand))
        self.addPage(SummaryPage(brand))
        self.addPage(InstallPage(brand, payload))
        self.addPage(FinishPage(brand))
        self.setButtonText(QWizard.WizardButton.NextButton, "Próximo")
        self.setButtonText(QWizard.WizardButton.BackButton, "Voltar")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancelar")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Concluir")

    def accept(self):
        target = Path(str(self.field("targetDir"))).expanduser()
        run_after = bool(self.field("runAfter"))
        super().accept()
        if run_after:
            subprocess.Popen([str(BIN_DIR / APP_ID)], start_new_session=True)


class RemovePage(QWizardPage):
    def __init__(self, icon: Path, target: Path):
        super().__init__()
        self.target = target
        self.done = False
        self.started = False
        layout = heading(self, "Removendo", "Aguarde enquanto os atalhos e arquivos são removidos.", icon)
        self.status = QLabel("Preparando desinstalação...")
        self.progress = QProgressBar()
        layout.addWidget(self.status)
        layout.addWidget(self.progress)
        layout.addStretch(1)

    def initializePage(self):
        if self.started:
            return
        self.started = True
        self.value = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(25)

    def tick(self):
        self.value += 2
        self.progress.setValue(min(self.value, 100))
        self.status.setText("Removendo atalhos..." if self.value < 55 else "Finalizando...")
        if self.value >= 100:
            self.timer.stop()
            self.done = True
            self.completeChanged.emit()
            QTimer.singleShot(250, self.wizard().next)

    def isComplete(self):
        return self.done


class UninstallWizard(QWizard):
    def __init__(self, target: Path):
        super().__init__()
        self.target = target
        icon = asset_path("uninstaller-icon.ico", None, target)
        brand = asset_path("logo-long.png", None, target)
        self.setWindowTitle(f"Desinstalar {APP_NAME}")
        self.setWindowIcon(QIcon(str(icon)))
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)
        self.setMinimumSize(760, 500)
        self.addPage(WelcomePage(brand, uninstall=True))
        self.addPage(RemovePage(brand, target))
        self.addPage(FinishPage(brand, uninstall=True))
        self.setButtonText(QWizard.WizardButton.NextButton, "Desinstalar")
        self.setButtonText(QWizard.WizardButton.CancelButton, "Cancelar")
        self.setButtonText(QWizard.WizardButton.FinishButton, "Concluir")

    def accept(self):
        cleanup = (
            "sleep 1; "
            f'rm -f "{BIN_DIR / APP_ID}" "{BIN_DIR / (APP_ID + "-uninstall")}"; '
            f'rm -f "{MENU_DIR / (APP_ID + ".desktop")}" "{MENU_DIR / (APP_ID + "-uninstall.desktop")}"; '
            f'rm -f "{HOME / "Desktop" / "Votu FieldOps.desktop"}"; '
            f'rm -f "{DATA_HOME / (APP_ID + ".location")}"; '
            f'rm -rf "{self.target}"'
        )
        super().accept()
        subprocess.Popen(["/bin/sh", "-c", cleanup], start_new_session=True)


def parse_args():
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--uninstall", action="store_true")
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--target", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName("VOTU Robotics")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f3f7f4"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#10231b"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#e7f0ea"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#0b1f17"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#176b4d"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#bce5ca"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#07150f"))
    app.setPalette(palette)
    app.setStyleSheet(STYLE)
    if args.install:
        if args.payload is None:
            return 2
        wizard = InstallWizard(args.payload.resolve())
    else:
        if args.target is None:
            return 2
        wizard = UninstallWizard(args.target.resolve())
    wizard.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
