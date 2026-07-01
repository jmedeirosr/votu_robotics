import logging
import time
from pathlib import Path

import customtkinter as ctk
import pandas as pd
import serial

#SER = serial.Serial("/dev/serial0", 9600, parity=serial.PARITY_NONE, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=1)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_PATH = PROJECT_ROOT / "assets"
LOG_PATH = PROJECT_ROOT / "logs" / "erros.log"
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


class ErrorDialog(ctk.CTkToplevel):
    def __init__(self, message):
        super().__init__()
        self.title("Erro!")
        self.resizable(False, False)

        self.message_label = ctk.CTkLabel(self, text=message, wraplength=250)
        self.message_label.pack(padx=10, pady=10)

        self.update_idletasks()

        width = self.message_label.winfo_reqwidth()
        height = self.message_label.winfo_reqheight()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        self.geometry(f"+{x}+{y}")

        self.ok_button = ctk.CTkButton(self, text="OK", command=self.destroy)
        self.ok_button.pack(pady=10)

        self.grab_set()


class MsgDialog(ctk.CTkToplevel):
    def __init__(self, title, message):
        super().__init__()
        self.title(title)
        self.resizable(False, False)
        self.configure(fg_color="#ffffff")
        self.set_dialog_icon()
        self.after(100, self.set_dialog_icon)
        self.after(500, self.set_dialog_icon)
        self.after(1000, self.set_dialog_icon)

        width = 420
        height = 300

        content = ctk.CTkFrame(
            self,
            fg_color="#ffffff",
            corner_radius=8,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        content.pack(fill="both", expand=True, padx=14, pady=14)

        logo_image = self.load_dialog_logo()
        if logo_image:
            self.logo_label = ctk.CTkLabel(content, text="", image=logo_image)
            self.logo_label.image = logo_image
            self.logo_label.pack(padx=22, pady=(22, 10))

        self.title_label = ctk.CTkLabel(
            content,
            text=title,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="normal"),
            text_color=TEXT_COLOR,
        )
        self.title_label.pack(padx=24, pady=(4, 8))

        self.message_label = ctk.CTkLabel(
            content,
            text=message,
            wraplength=330,
            justify="left",
            font=ctk.CTkFont(family="Segoe UI", size=13, weight="normal"),
            text_color=MUTED_COLOR,
        )
        self.message_label.pack(fill="x", padx=32, pady=(0, 18))

        self.ok_button = ctk.CTkButton(
            content,
            text="OK",
            command=self.destroy,
            fg_color=ACCENT_COLOR,
            hover_color=ACCENT_HOVER,
            height=38,
            corner_radius=8,
        )
        self.ok_button.pack(fill="x", padx=32, pady=(0, 22))

        self.update_idletasks()

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        self.geometry(f"{width}x{height}+{x}+{y}")

        self.grab_set()

    def load_dialog_logo(self):
        if not LOGO_PATH.exists():
            return None

        try:
            from PIL import Image

            image = Image.open(LOGO_PATH)
            return ctk.CTkImage(light_image=image, dark_image=image, size=(220, 57))
        except Exception as e:
            logger.error(f"Error loading dialog logo: {e}")
            return None

    def set_dialog_icon(self):
        try:
            if ICON_PATH.exists():
                self.iconbitmap(default=str(ICON_PATH))
                self.wm_iconbitmap(default=str(ICON_PATH))
                if not hasattr(self, "dialog_icon_photo"):
                    from PIL import Image, ImageTk

                    image = Image.open(ICON_PATH)
                    self.dialog_icon_photo = ImageTk.PhotoImage(image)
                self.iconphoto(False, self.dialog_icon_photo)
        except Exception as e:
            logger.error(f"Error setting dialog icon: {e}")


def send_serial(value: int) -> bool:
    try:
        value = int(str(value).replace("➤", "").strip())
        if value >= 10:
            encoded = str(value).encode()
        else:
            encoded = f"0{value}".encode()
        #SER.write(encoded)
        #SER.flush()
        print (encoded)
        while True:
            #returned_data = str(SER.readline(10), "ascii")
            #if returned_data == "F":
               # print (returned_data)
                break
        return True
    except Exception as e:
        logger.error(f"Error in send_serial: {e}")
        ErrorDialog("Erro ao enviar dados para a máquina.")
