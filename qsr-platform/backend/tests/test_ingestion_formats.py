"""Regression tests for the auto-detecting ingestion layer.

Covers every bug found in the audit plus the required source formats:
standard CSV, TSV, MT4 (header-less dotted dates), MT5 (tab + <...> headers),
header/no-header, delimiter/format auto-detection, epoch timestamps, and the
fail-closed handling of unparseable timestamps / prices.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import polars as pl
import pytest

from qsr.data.ingestion.column_mapping import ColumnMapping
from qsr.data.ingestion.detect import (
    detect_datetime_format,
    epoch_unit_for,
    looks_like_header,
    map_named_columns,
    positional_mapping,
    sniff_delimiter,
)
from qsr.data.ingestion.errors import IngestionError
from qsr.data.ingestion.readers import CsvReader
from qsr.data.ingestion.schema import CLOSE, HIGH, LOW, OPEN, TS, VOLUME
from qsr.data.validation.base import ValidationContext
from qsr.data.validation.pipeline import ValidationPipeline
from qsr.data.validation.report import IssueCode
from qsr.domain.instruments.session_calendar import ForexWeekendCalendar
from qsr.domain.market_data.timeframe import Timeframe

M1 = Timeframe.from_label("M1")
CTX = ValidationContext(M1, ForexWeekendCalendar())


def _read(tmp_path: Path, name: str, text: str, mapping: ColumnMapping | None = None):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return CsvReader().read(p, mapping)


def _assert_canonical(df: pl.DataFrame) -> None:
    assert df.columns == [TS, OPEN, HIGH, LOW, CLOSE, VOLUME]
    assert df.schema[TS] == pl.Datetime("us", "UTC")
    assert df.schema[OPEN] == pl.Float64
    assert df.get_column(TS).null_count() == 0


# --- format matrix ---------------------------------------------------------

def test_standard_csv_combined_datetime(tmp_path):
    df = _read(tmp_path, "std.csv",
               "Datetime,Open,High,Low,Close,Volume\n"
               "2024-01-02 09:00:00,1.1,1.2,1.0,1.15,100\n"
               "2024-01-02 09:01:00,1.15,1.25,1.05,1.2,110\n")
    _assert_canonical(df)
    assert df.height == 2
    assert df.get_column(TS)[0] == datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)


def test_standard_csv_split_date_time_no_hints(tmp_path):
    df = _read(tmp_path, "split.csv",
               "Date,Time,Open,High,Low,Close,Volume\n"
               "2024-01-02,09:00,1.1,1.2,1.0,1.15,100\n"
               "2024-01-02,09:01,1.1,1.2,1.0,1.15,100\n")
    _assert_canonical(df)
    assert df.height == 2


def test_tsv(tmp_path):
    df = _read(tmp_path, "data.tsv",
               "Date\tTime\tOpen\tHigh\tLow\tClose\tVolume\n"
               "2024-01-02\t09:00\t1.1\t1.2\t1.0\t1.15\t100\n"
               "2024-01-02\t09:01\t1.1\t1.2\t1.0\t1.15\t100\n")
    _assert_canonical(df)
    assert df.height == 2


def test_mt4_headerless_dotted_dates(tmp_path):
    # MT4 export: no header, YYYY.MM.DD dates, comma-separated, with volume.
    df = _read(tmp_path, "mt4.csv",
               "2024.01.02,09:00,1.10000,1.10050,1.09950,1.10020,100\n"
               "2024.01.02,09:01,1.10020,1.10080,1.10000,1.10060,120\n")
    _assert_canonical(df)
    assert df.height == 2
    assert df.get_column(TS)[0] == datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)
    assert df.get_column(VOLUME)[0] == 100.0


def test_mt5_tab_bracket_headers(tmp_path):
    df = _read(tmp_path, "mt5.csv",
               "<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\t<TICKVOL>\t<VOL>\t<SPREAD>\n"
               "2024.01.02\t09:00:00\t1.1\t1.2\t1.0\t1.15\t100\t0\t2\n"
               "2024.01.02\t09:01:00\t1.15\t1.25\t1.05\t1.2\t110\t0\t2\n")
    _assert_canonical(df)
    assert df.height == 2
    assert df.get_column(TS)[1] == datetime(2024, 1, 2, 9, 1, tzinfo=timezone.utc)


def test_headerless_combined_datetime(tmp_path):
    df = _read(tmp_path, "nohdr.csv",
               "2024-01-02 09:00:00,1.1,1.2,1.0,1.15,100\n"
               "2024-01-02 09:01:00,1.1,1.2,1.0,1.15,100\n")
    _assert_canonical(df)
    assert df.height == 2


def test_semicolon_delimiter(tmp_path):
    df = _read(tmp_path, "semi.csv",
               "Date;Time;Open;High;Low;Close;Volume\n"
               "2024-01-02;09:00;1.1;1.2;1.0;1.15;100\n"
               "2024-01-02;09:01;1.1;1.2;1.0;1.15;100\n")
    _assert_canonical(df)
    assert df.height == 2


def test_epoch_seconds(tmp_path):
    # 2024-01-02 09:00:00 UTC == 1704186000
    df = _read(tmp_path, "epoch.csv",
               "timestamp,open,high,low,close,volume\n"
               "1704186000,1.1,1.2,1.0,1.15,100\n"
               "1704186060,1.1,1.2,1.0,1.15,100\n")
    _assert_canonical(df)
    assert df.get_column(TS)[0] == datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)


def test_epoch_millis(tmp_path):
    df = _read(tmp_path, "epochms.csv",
               "timestamp,open,high,low,close,volume\n"
               "1704186000000,1.1,1.2,1.0,1.15,100\n"
               "1704186060000,1.1,1.2,1.0,1.15,100\n")
    _assert_canonical(df)
    assert df.get_column(TS)[0] == datetime(2024, 1, 2, 9, 0, tzinfo=timezone.utc)


def test_missing_volume_defaults_zero(tmp_path):
    df = _read(tmp_path, "novol.csv",
               "Datetime,Open,High,Low,Close\n"
               "2024-01-02 09:00:00,1.1,1.2,1.0,1.15\n")
    assert df.get_column(VOLUME)[0] == 0.0


def test_source_tz_converted_to_utc(tmp_path):
    df = _read(tmp_path, "nytz.csv",
               "Datetime,Open,High,Low,Close,Volume\n"
               "2024-01-02 09:00:00,1.1,1.2,1.0,1.15,100\n",
               ColumnMapping(source_tz="America/New_York"))
    # 09:00 EST (UTC-5) -> 14:00 UTC
    assert df.get_column(TS)[0] == datetime(2024, 1, 2, 14, 0, tzinfo=timezone.utc)


# --- fail-closed / informative errors --------------------------------------

def test_missing_ohlc_column_raises_ingestion_error(tmp_path):
    with pytest.raises(IngestionError) as ei:
        _read(tmp_path, "bad.csv",
              "Datetime,Open,High,Close,Volume\n"  # no Low
              "2024-01-02 09:00:00,1.1,1.2,1.15,100\n")
    assert "low" in str(ei.value).lower()


def test_unparseable_timestamp_rejected_not_persisted(tmp_path):
    # Wrong explicit format -> null timestamps -> must be flagged as ERROR.
    df = _read(tmp_path, "badts.csv",
               "Date,Time,Open,High,Low,Close,Volume\n"
               "2024-01-02,09:00:05,1.1,1.2,1.0,1.15,100\n",
               ColumnMapping(date="Date", time="Time", datetime_format="%Y-%m-%d %H:%M"))
    report = ValidationPipeline().run(df, CTX)
    assert report.has_errors
    codes = {i.code for i in report.issues}
    assert IssueCode.NULL_TIMESTAMP in codes


def test_single_row_null_timestamp_is_error(tmp_path):
    # Regression: a single unparseable row used to persist silently.
    df = _read(tmp_path, "one.csv",
               "Date,Time,Open,High,Low,Close,Volume\n"
               "2024-01-02,09:00:05,1.1,1.2,1.0,1.15,100\n",
               ColumnMapping(date="Date", time="Time", datetime_format="%Y-%m-%d %H:%M"))
    report = ValidationPipeline().run(df, CTX)
    assert report.has_errors


def test_non_numeric_price_flagged(tmp_path):
    df = _read(tmp_path, "badprice.csv",
               "Datetime,Open,High,Low,Close,Volume\n"
               "2024-01-02 09:00:00,abc,1.2,1.0,1.15,100\n"
               "2024-01-02 09:01:00,1.1,1.2,1.0,1.15,100\n")
    report = ValidationPipeline().run(df, CTX)
    assert report.has_errors
    assert IssueCode.INVALID_OHLC in {i.code for i in report.issues}


def test_empty_file_raises(tmp_path):
    with pytest.raises(IngestionError):
        _read(tmp_path, "empty.csv", "")


# --- detection unit tests --------------------------------------------------

def test_sniff_delimiter():
    assert sniff_delimiter("a,b,c\n1,2,3") == ","
    assert sniff_delimiter("a\tb\tc\n1\t2\t3") == "\t"
    assert sniff_delimiter("a;b;c\n1;2;3") == ";"
    assert sniff_delimiter("a|b|c\n1|2|3") == "|"


def test_looks_like_header():
    assert looks_like_header(["Date", "Open", "High"])
    assert looks_like_header(["<DATE>", "<OPEN>"])
    assert not looks_like_header(["2024.01.02", "14:30", "1.1", "1.2"])


def test_detect_datetime_format():
    # Full-second timestamps resolve to the optional-fraction (%.f) variant,
    # which Polars parses whether or not a fraction is present.
    assert detect_datetime_format(["2024-01-02 09:00:00"]) == "%Y-%m-%d %H:%M:%S%.f"
    assert detect_datetime_format(["2024.01.02 09:00"]) == "%Y.%m.%d %H:%M"
    assert detect_datetime_format(["2024-01-02T09:00:00"]) == "%Y-%m-%dT%H:%M:%S%.f"
    assert detect_datetime_format(["not a date"]) is None


def test_epoch_unit_for():
    assert epoch_unit_for(1704186000) == "s"
    assert epoch_unit_for(1704186000000) == "ms"
    assert epoch_unit_for(1704186000000000) == "us"


def test_map_named_columns_synonyms():
    m = map_named_columns(["<DATE>", "<TIME>", "<OPEN>", "<HIGH>", "<LOW>",
                           "<CLOSE>", "<TICKVOL>"], ColumnMapping())
    assert m.date == "<DATE>" and m.time == "<TIME>"
    assert m.open == "<OPEN>" and m.close == "<CLOSE>"
    assert m.volume == "<TICKVOL>"


def test_positional_mapping_mt4():
    m = positional_mapping(["2024.01.02", "09:00", "1.1", "1.2", "1.0", "1.15", "100"],
                           ColumnMapping())
    assert m.date == "column_1" and m.time == "column_2"
    assert m.open == "column_3" and m.volume == "column_7"
