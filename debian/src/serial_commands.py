import logging
import time
from pathlib import Path

import pandas as pd
import serial
from PyQt6.QtWidgets import QMessageBox
from runtime_paths import resource_path, user_state_path

SER = serial.Serial("/dev/serial0", 9600, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=1)

ASSETS_PATH = resource_path("assets")
LOG_PATH = user_state_path() / "erros.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    filename=LOG_PATH,
    level=logging.ERROR,
    format="%(asctime)s:%(levelname)s:%(message)s",
)
logger = logging.getLogger(__name__)

LOGO_PATH = ASSETS_PATH / "logo-long.png"
ICON_PATH = ASSETS_PATH / "logo-icon.ico"

TEXT_COLOR = "#172033"
MUTED_COLOR = "#637083"
ACCENT_COLOR = "#1f7a4d"
ACCENT_HOVER = "#17633e"
BORDER_COLOR = "#d8dee8"


def get_tier_column(df: pd.DataFrame) -> pd.Series:
    if "Tier#" in df.columns:
        return "Tier#"
    if "Tier" in df.columns:
        return "Tier"
    return None


def read_data_from_excel(file_path : str):
    df = pd.read_excel(file_path)
    columns = ["Entry #", "Book Name", "Entry Book Name"]
    optional_columns = ["Plot #", "PLOT#", "B-Plot#", "Range", "Tier#", "Tier"]
    columns.extend(column for column in optional_columns if column in df.columns)
    return df[columns]


def booknames_list(df: pd.DataFrame, selected_entry=None, selected_tier=None):
    filtered_df = df
    if selected_entry:
        filtered_df = filtered_df[filtered_df["Entry Book Name"] == selected_entry]

    tier_column = get_tier_column(filtered_df)
    if selected_tier and tier_column:
        filtered_df = filtered_df[filtered_df[tier_column].astype(str) == str(selected_tier)]

    return filtered_df["Book Name"].dropna().unique()


def entries_list(df: pd.DataFrame):
    return df["Entry Book Name"].dropna().unique()


def tiers_list(df: pd.DataFrame, selected_entry: str):
    tier_column = get_tier_column(df)
    if not tier_column:
        return []

    filtered_df = df[df["Entry Book Name"] == selected_entry]
    return sorted(filtered_df[tier_column].dropna().unique())


def ErrorDialog(message):
    """Show errors with the same Qt toolkit used by the main application."""
    QMessageBox.critical(None, "Erro!", message)


def send_serial(value: int) -> bool:
    try:
        value = int(str(value).replace("➤", "").strip())
        if value >= 10:
            encoded = str(value).encode()
        else:
            encoded = f"0{value}".encode()
        SER.write(encoded)
        SER.flush()
        print (encoded)
        while True:
            returned_data = str(SER.readline(10), "ascii")
            if returned_data == "F":
                print (returned_data)
                break
        return True
    except Exception as e:
        logger.error(f"Error in send_serial: {e}")
        ErrorDialog("Erro ao enviar dados para a máquina.")
