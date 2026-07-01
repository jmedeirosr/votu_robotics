import pandas as pd
from serial_commands import logger

POT_COUNT = 96


def filter_by_bookname(df: pd.DataFrame, book_name: str, entry: str, tier=None):
    try:
        filtered_df = df[
            (df["Book Name"] == book_name) & (df["Entry Book Name"] == entry)
        ]
        tier_col = get_column(filtered_df, "Tier#", "Tier")
        if tier is not None and tier_col is not None:
            filtered_df = filtered_df[filtered_df[tier_col].astype(str) == str(tier)]
        return filtered_df
    except Exception as e:
        logger.error(f"Error in filter_by_bookname: {e}")
        return None


def get_column(df: pd.DataFrame, *names):
    for name in names:
        if name in df.columns:
            return name
    return None


def has_plot_columns(df: pd.DataFrame):
    return (
        get_column(df, "Entry #", "Entry") is not None
        and get_column(df, "Plot #", "PLOT#", "B-Plot#") is not None
        and get_column(df, "Range") is not None
        and get_column(df, "Tier#", "Tier") is not None
    )


def process_data_by_plot(entries_df: pd.DataFrame, parcels_per_row: int):
    try:
        if entries_df is None or entries_df.empty:
            logger.error("No entries found for selected Book Name and Entry Book Name.")
            return None
        if parcels_per_row < 1 or parcels_per_row > 16:
            logger.error("Parcels per row must be between 1 and 16.")
            return None

        entry_col = get_column(entries_df, "Entry #", "Entry")
        plot_col = get_column(entries_df, "Plot #", "PLOT#", "B-Plot#")
        range_col = get_column(entries_df, "Range")
        tier_col = get_column(entries_df, "Tier#", "Tier")

        selected_columns = [entry_col, plot_col, range_col, tier_col]
        positioned_df = entries_df[selected_columns].copy()
        positioned_df = positioned_df.dropna(subset=[entry_col, plot_col, range_col])

        if len(positioned_df.index) != POT_COUNT:
            logger.error(
                f"Expected {POT_COUNT} pots, found {len(positioned_df.index)}."
            )
            return None

        positioned_df = positioned_df.sort_values(
            by=[tier_col, range_col, plot_col], kind="stable"
        )

        entry_rows = []
        range_rows = []
        plot_rows = []
        for row_index, start in enumerate(range(0, len(positioned_df), parcels_per_row)):
            row_df = positioned_df.iloc[start : start + parcels_per_row]
            entry_values = row_df[entry_col].to_list()
            range_values = row_df[range_col].to_list()
            plot_values = row_df[plot_col].to_list()
            if row_index % 2 == 1:
                entry_values.reverse()
                range_values.reverse()
                plot_values.reverse()
            entry_rows.append(entry_values)
            range_rows.append(range_values)
            plot_rows.append(plot_values)

        entry_rows = [
            row + [0] * (parcels_per_row - len(row))
            for row in entry_rows
        ]
        range_rows = [
            row + [""] * (parcels_per_row - len(row))
            for row in range_rows
        ]
        plot_rows = [
            row + [""] * (parcels_per_row - len(row))
            for row in plot_rows
        ]

        entry_rows.reverse()
        range_rows.reverse()
        plot_rows.reverse()

        result = pd.DataFrame(entry_rows)
        result.columns = range(1, len(result.columns) + 1)
        range_matrix = pd.DataFrame(range_rows)
        range_matrix.columns = result.columns
        plot_matrix = pd.DataFrame(plot_rows)
        plot_matrix.columns = result.columns

        if int((result != 0).sum().sum()) != POT_COUNT:
            logger.error(f"Generated matrix does not have {POT_COUNT} pots.")
            return None

        result = result.reset_index(drop=True)
        result.attrs["range_matrix"] = range_matrix.reset_index(drop=True)
        result.attrs["plot_matrix"] = plot_matrix.reset_index(drop=True)
        return result
    except Exception as e:
        logger.error(f"Error in process_data_by_plot: {e}")
        return None


def main(df, parcels_per_row, book_name=None, entry=None, tier=None):
    try:
        entries_df = filter_by_bookname(df, book_name, entry, tier)
        if has_plot_columns(entries_df):
            result = process_data_by_plot(entries_df, parcels_per_row)
        else:
            logger.error("Spreadsheet does not contain Plot, Range, Entry and Tier columns.")
            result = None
        return result
    except Exception as e:
        logger.error(f"Error in main: {e}")
        return None
