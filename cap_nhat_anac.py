
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import shutil
import tempfile
import unicodedata

from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ==================================================
# 1. CAU HINH DU AN
# ==================================================

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "DuLieu_DaXuLy"

AUT = DATA / "_tu_dong"
STATE = AUT / "state.json"
PARTS = AUT / "parts"
BASELINE = AUT / "baseline_2024"

CONFIG = ROOT / "nguon_anac.json"

OUTPUT = {
    "month": "tong_hop_theo_thang_2024.csv",
    "domestic": "top100_noi_dia_toa_do.csv",
    "international": "top100_quoc_te_toa_do.csv",
    "dest": "xu_huong_diem_den_2024.csv",
}

ROOT_URL = {
    "domestic": "https://sas.anac.gov.br/sas/tarifadomestica/",
    "international": "https://sas.anac.gov.br/sas/tarifainternacional/",
}


# ==================================================
# 2. CHUAN HOA TEN COT ANAC
# Ho tro ca cau truc cu va moi tu thang 03/2025
# ==================================================

ALIASES = {
    "origin": [
        "ORIGEM",
        "AEROPORTO_ORIGEM",
        "ICAO_AERODROMO_ORIGEM",
        "ICAO_ORIGEM",
        "ICAO_AEROPORTO_ORIGEM",
        "SG_ICAO_ORIGEM",
    ],
    "destination": [
        "DESTINO",
        "AEROPORTO_DESTINO",
        "ICAO_AERODROMO_DESTINO",
        "ICAO_DESTINO",
        "ICAO_AEROPORTO_DESTINO",
        "SG_ICAO_DESTINO",
    ],
    "seats": [
        "ASSENTOS",
        "ASSENTOS_COMERCIALIZADOS",
        "QUANTIDADE_ASSENTOS",
        "QTDE_ASSENTOS",
        "QUANTIDADE_DE_ASSENTOS",
        "NR_ASSENTOS",
    ],
    "fare": [
        "TARIFA",
        "VALOR_TARIFA",
        "TARIFA_N",
        "TARIFA_VOO",
        "VALOR_DA_TARIFA",
        "VALOR",
        "PRECO",
        "GIA_VE",
        "NR_TARIFA",
    ],
    "year": [
        "ANO",
        "ANO_REFERENCIA",
        "ANO_VENDA",
        "NR_ANO_REFERENCIA",
    ],
    "month": [
        "MES",
        "MES_REFERENCIA",
        "MES_VENDA",
        "THANG",
        "NR_MES_REFERENCIA",
    ],
    "group": [
        "GRUPO",
        "GRUPO_TARIFA",
        "GRUPO_TARIFARIO",
        "GRUPO_DA_TARIFA",
    ],
}


# ==================================================
# 3. HAM DOC VA CHUAN HOA DU LIEU
# ==================================================

class Links(HTMLParser):

    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            value = dict(attrs).get("href")
            if value:
                self.links.append(value)


def normalize(s):
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(
        x for x in s
        if unicodedata.category(x) != "Mn"
    )
    return re.sub(
        r"[^A-Z0-9]+", "_", s.upper()
    ).strip("_")


def col(columns, kind, required=True):
    have = {
        normalize(c): c
        for c in columns
    }

    for name in ALIASES[kind]:
        key = normalize(name)

        if key in have:
            return have[key]

    if required:
        raise ValueError(
            f"Khong tim thay cot {kind}. "
            f"Cac cot hien co: {list(columns)}"
        )

    return None


def num(series):
    s = (
        series.astype("string")
        .str.strip()
        .str.replace(
            r"[^\d,.\-]", "", regex=True
        )
    )

    comma = s.str.contains(
        ",", regex=False
    ).fillna(False)

    dot = s.str.contains(
        ".", regex=False
    ).fillna(False)

    both = comma & dot

    comma_decimal = both & (
        s.str.rfind(",") > s.str.rfind(".")
    )

    dot_decimal = both & ~comma_decimal

    s.loc[comma_decimal] = (
        s.loc[comma_decimal]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
    )

    s.loc[dot_decimal] = (
        s.loc[dot_decimal]
        .str.replace(",", "", regex=False)
    )

    s.loc[comma & ~dot] = (
        s.loc[comma & ~dot]
        .str.replace(",", ".", regex=False)
    )

    return pd.to_numeric(
        s, errors="coerce"
    )


def read_csv(path):
    path = Path(path)

    with path.open(
        "r", encoding="utf-8-sig"
    ) as f:
        header = f.readline()

    sep = (
        ";" if header.count(";") > header.count(",")
        else ","
    )

    df = pd.read_csv(
        path,
        sep=sep,
        encoding="utf-8-sig",
        low_memory=False
    )

    if len(df.columns) == 1:
        raise ValueError(
            f"File {path.name} chi doc duoc 1 cot."
        )

    return df


def save_csv(path, df):
    path.parent.mkdir(
        parents=True, exist_ok=True
    )

    df.to_csv(
        path,
        index=False,
        encoding="utf-8-sig"
    )


# ==================================================
# 4. KIEM TRA VA BAO VE DU LIEU 2024
# ==================================================

def validate_2024(df):

    required = {
        "THANG",
        "LOAI_CHUYEN_BAY",
        "SO_GHE_BAN",
        "GIA_BINH_QUAN"
    }

    missing = required - set(df.columns)

    if missing:
        raise ValueError(
            f"Du lieu 2024 thieu cot: {sorted(missing)}"
        )

    df = df.copy()

    df["THANG"] = (
        df["THANG"]
        .astype("string")
        .str.strip()
    )

    df["LOAI_CHUYEN_BAY"] = (
        df["LOAI_CHUYEN_BAY"]
        .astype("string")
        .str.strip()
    )

    expected = {
        f"2024-{m:02d}"
        for m in range(1, 13)
    }

    for market in ["Noi dia", "Quoc te"]:

        actual = set(
            df.loc[
                df["LOAI_CHUYEN_BAY"].eq(market),
                "THANG"
            ]
        )

        missing_months = expected - actual

        if missing_months:
            raise ValueError(
                f"Du lieu 2024 cua {market} "
                f"thieu thang: {sorted(missing_months)}"
            )

    for c in ["SO_GHE_BAN", "GIA_BINH_QUAN"]:
        df[c] = pd.to_numeric(
            df[c], errors="coerce"
        )

    if df[
        ["SO_GHE_BAN", "GIA_BINH_QUAN"]
    ].isna().any().any():

        raise ValueError(
            "Gia ve hoac so ghe nam 2024 khong hop le."
        )

    return df


# ==================================================
# 5. KET NOI VA TIM FILE ANAC
# ==================================================

def session():
    s = requests.Session()

    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; ANAC-student-ETL/2.0)"
        ),
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"
    })

    retry = Retry(
        total=3,
        connect=3,
        read=2,
        backoff_factor=1.5,
        status_forcelist=[
            429, 500, 502, 503, 504
        ]
    )

    s.mount(
        "https://",
        HTTPAdapter(max_retries=retry)
    )

    return s


def index_files(sess, kind, year):

    url = ROOT_URL[kind] + f"{year}/"

    response = sess.get(
        url, timeout=35
    )

    response.raise_for_status()

    html = response.text

    if (
        "<html" not in html.lower()
        and "<a " not in html.lower()
    ):
        raise ValueError(
            "ANAC khong tra ve danh muc HTML"
        )

    parser = Links()
    parser.feed(html)

    found = {}

    for href in parser.links:

        name = urlsplit(href).path.rsplit("/", 1)[-1]

        if kind == "domestic":
            match = re.fullmatch(
                r"(\d{4})(\d{2})\.csv",
                name,
                re.I
            )
        else:
            match = re.fullmatch(
                r"Internacional_(\d{4})-(\d{2})\.(csv|txt)",
                name,
                re.I
            )

        if not match:
            continue

        yy = int(match.group(1))
        mm = int(match.group(2))

        if yy != year or not 1 <= mm <= 12:
            continue

        link = urljoin(url, href)

        if urlsplit(link).hostname != "sas.anac.gov.br":
            continue

        found[f"{year}-{mm:02d}"] = link

    return found


def download(
    sess,
    url,
    destination,
    max_bytes=600_000_000
):

    if urlsplit(url).scheme != "https":
        raise ValueError(
            "Chi chap nhan HTTPS"
        )

    total = 0
    sha = hashlib.sha256()

    with sess.get(
        url,
        stream=True,
        timeout=(20, 120)
    ) as response:

        response.raise_for_status()

        content_type = response.headers.get(
            "content-type", ""
        ).lower()

        if "text/html" in content_type:
            raise ValueError(
                "Nguon tra ve HTML thay vi CSV"
            )

        with destination.open("wb") as f:

            for block in response.iter_content(
                chunk_size=1024 * 1024
            ):

                if not block:
                    continue

                total += len(block)

                if total > max_bytes:
                    raise ValueError(
                        "File vuot qua 600 MB"
                    )

                sha.update(block)
                f.write(block)

    with destination.open("rb") as f:
        head = f.read(120).lstrip().lower()

    if (
        total < 40
        or head.startswith((b"<html", b"<!doctype"))
    ):
        raise ValueError(
            "File tai ve khong phai CSV hop le"
        )

    return sha.hexdigest()


# ==================================================
# 6. EXTRACT VA TRANSFORM TUNG THANG
# ==================================================

def read_chunks(path, period, kind):

    with path.open("rb") as f:
        header = f.readline().decode("latin-1")

    sep = (
        ";" if header.count(";") >= header.count(",")
        else ","
    )

    reader = pd.read_csv(
        path,
        sep=sep,
        encoding="latin-1",
        dtype="string",
        chunksize=80000,
        low_memory=False,
        on_bad_lines="error"
    )

    parts = []

    seats_total = 0.0
    fare_weight = 0.0
    fare_seats = 0.0
    valid_rows = 0

    for chunk in reader:

        if chunk.empty:
            continue

        origin = col(chunk.columns, "origin")
        dest = col(chunk.columns, "destination")
        seats = col(chunk.columns, "seats")
        fare = col(chunk.columns, "fare")

        yy = col(chunk.columns, "year", False)
        mm = col(chunk.columns, "month", False)
        gg = col(chunk.columns, "group", False)

        if yy is not None:
            mask = num(chunk[yy]).eq(
                int(period[:4])
            ).fillna(False)

            chunk = chunk.loc[mask].copy()

        if mm is not None:
            mask = num(chunk[mm]).eq(
                int(period[5:])
            ).fillna(False)

            chunk = chunk.loc[mask].copy()

        if (
            gg is not None
            and int(period[:4]) >= 2026
            and kind == "domestic"
        ):

            group = (
                chunk[gg]
                .astype("string")
                .str.strip()
                .str.upper()
            )

            chunk = chunk[
                group.isin([
                    "1", "I", "GRUPO I", "GRUPO 1"
                ])
            ].copy()

        if chunk.empty:
            continue

        df = pd.DataFrame({
            "ORIGEM": (
                chunk[origin].str.strip().str.upper()
            ),
            "DESTINO": (
                chunk[dest].str.strip().str.upper()
            ),
            "ASSENTOS": num(chunk[seats]),
            "TARIFA": num(chunk[fare])
        })

        df = df.dropna(
            subset=[
                "ORIGEM",
                "DESTINO",
                "ASSENTOS"
            ]
        )

        valid_codes = (
            df["ORIGEM"].str.fullmatch(
                r"[A-Z0-9]{4}", na=False
            )
            &
            df["DESTINO"].str.fullmatch(
                r"[A-Z0-9]{4}", na=False
            )
        )

        df = df.loc[valid_codes]

        df = df[
            (df["ASSENTOS"] > 0)
            &
            (df["ASSENTOS"] % 1 == 0)
        ]

        if df.empty:
            continue

        df["TARIFA_VALID"] = (
            df["TARIFA"].where(
                df["TARIFA"] > 0
            )
        )

        df["GIA_NHAN_GHE"] = (
            df["TARIFA_VALID"].fillna(0)
            * df["ASSENTOS"]
        )

        df["GHE_CO_GIA"] = (
            df["ASSENTOS"].where(
                df["TARIFA_VALID"].notna(),
                0
            )
        )

        part = df.groupby(
            ["ORIGEM", "DESTINO"],
            as_index=False
        ).agg(
            ASSENTOS=("ASSENTOS", "sum"),
            GIA_NHAN_GHE=("GIA_NHAN_GHE", "sum"),
            GHE_CO_GIA=("GHE_CO_GIA", "sum")
        )

        parts.append(part)

        seats_total += float(
            df["ASSENTOS"].sum()
        )

        fare_weight += float(
            df["GIA_NHAN_GHE"].sum()
        )

        fare_seats += float(
            df["GHE_CO_GIA"].sum()
        )

        valid_rows += len(df)

    if (
        not parts
        or seats_total <= 0
        or fare_seats <= 0
    ):
        raise ValueError(
            f"Khong co du lieu hop le: "
            f"{kind} {period}"
        )

    routes = (
        pd.concat(parts)
        .groupby(
            ["ORIGEM", "DESTINO"],
            as_index=False
        )[
            [
                "ASSENTOS",
                "GIA_NHAN_GHE",
                "GHE_CO_GIA"
            ]
        ]
        .sum()
    )

    routes.insert(0, "THANG", period)

    routes.insert(
        1,
        "LOAI",
        "Nội địa" if kind == "domestic"
        else "Quốc tế"
    )

    info = {
        "month": period,
        "market": kind,
        "seats": seats_total,
        "fare_weight": fare_weight,
        "fare_seats": fare_seats,
        "rows": valid_rows
    }

    return routes, info


# ==================================================
# 7. TICH HOP SAN BAY OURAIRPORTS
# ==================================================

def load_airports(sess, cfg, tempdir):

    cache = AUT / "airports.csv"

    if cache.exists():
        air = pd.read_csv(
            cache, low_memory=False
        )

    else:
        target = tempdir / "airports.csv"

        download(
            sess,
            cfg["airports_url"],
            target,
            max_bytes=70_000_000
        )

        air = pd.read_csv(
            target, low_memory=False
        )

        AUT.mkdir(
            parents=True, exist_ok=True
        )

        shutil.copy2(target, cache)

    cols = [
        "ident", "name", "municipality",
        "iso_country", "latitude_deg",
        "longitude_deg"
    ]

    for c in cols:
        if c not in air:
            raise ValueError(
                f"OurAirports thieu cot: {c}"
            )

    air = air[cols].rename(columns={
        "ident": "CODE",
        "name": "NAME",
        "municipality": "CITY",
        "iso_country": "COUNTRY",
        "latitude_deg": "LAT",
        "longitude_deg": "LON"
    })

    air["CODE"] = (
        air["CODE"]
        .astype("string")
        .str.strip()
        .str.upper()
    )

    air = (
        air.dropna(subset=["CODE"])
        .drop_duplicates("CODE")
    )

    air["LAT"] = pd.to_numeric(
        air["LAT"], errors="coerce"
    )

    air["LON"] = pd.to_numeric(
        air["LON"], errors="coerce"
    )

    if not air["CODE"].eq("SPJC").any():

        extra = pd.DataFrame([{
            "CODE": "SPJC",
            "NAME": "Jorge Chávez International Airport",
            "CITY": "Lima",
            "COUNTRY": "PE",
            "LAT": -12.0219,
            "LON": -77.1143
        }])

        air = pd.concat(
            [air, extra],
            ignore_index=True
        )

    return air


# ==================================================
# 8. KET HOP DU LIEU 2024 - 2026
# ==================================================

def build_combined(airports, state, staged):

    oldm = validate_2024(
        read_csv(BASELINE / OUTPUT["month"])
    )

    oldd = read_csv(
        BASELINE / OUTPUT["dest"]
    )

    oldr = {
        kind: read_csv(BASELINE / OUTPUT[kind])
        for kind in ("domestic", "international")
    }

    for kind in oldr:
        if "NAM" not in oldr[kind]:
            oldr[kind]["NAM"] = 2024

    months = [oldm]
    destinations = [oldd]

    route_years = {
        kind: [oldr[kind]]
        for kind in oldr
    }

    pieces = []

    for key in state["months"]:

        path = PARTS / (key + ".csv")

        if not path.exists():
            raise FileNotFoundError(
                f"Thieu bang ETL: {path}"
            )

        pieces.append(read_csv(path))

    if pieces:

        allroutes = pd.concat(
            pieces,
            ignore_index=True
        )

        monthly = (
            allroutes.groupby(
                ["THANG", "LOAI"],
                as_index=False
            )[
                [
                    "ASSENTOS",
                    "GIA_NHAN_GHE",
                    "GHE_CO_GIA"
                ]
            ]
            .sum()
        )

        monthly["LOAI_CHUYEN_BAY"] = (
            monthly["LOAI"].map({
                "Nội địa": "Noi dia",
                "Quốc tế": "Quoc te"
            })
        )

        monthly["SO_GHE_BAN"] = (
            monthly["ASSENTOS"]
        )

        monthly["GIA_BINH_QUAN"] = (
            monthly["GIA_NHAN_GHE"]
            / monthly["GHE_CO_GIA"]
        )

        months.append(
            monthly[
                [
                    "THANG",
                    "LOAI_CHUYEN_BAY",
                    "SO_GHE_BAN",
                    "GIA_BINH_QUAN"
                ]
            ]
        )

        allroutes["NAM"] = (
            allroutes["THANG"]
            .str[:4]
            .astype(int)
        )

        yearly = (
            allroutes.groupby(
                [
                    "NAM", "LOAI",
                    "ORIGEM", "DESTINO"
                ],
                as_index=False
            )["ASSENTOS"]
            .sum()
        )

        origin_air = airports[
            ["CODE", "NAME", "LAT", "LON"]
        ].rename(columns={
            "CODE": "ORIGEM",
            "NAME": "TEN_DI",
            "LAT": "LAT_DI",
            "LON": "LON_DI"
        })

        dest_air = airports[
            ["CODE", "NAME", "LAT", "LON"]
        ].rename(columns={
            "CODE": "DESTINO",
            "NAME": "TEN_DEN",
            "LAT": "LAT_DEN",
            "LON": "LON_DEN"
        })

        yearly = yearly.merge(
            origin_air,
            on="ORIGEM",
            how="left",
            validate="many_to_one"
        )

        yearly = yearly.merge(
            dest_air,
            on="DESTINO",
            how="left",
            validate="many_to_one"
        )

        yearly = yearly.dropna(
            subset=[
                "LAT_DI", "LON_DI",
                "LAT_DEN", "LON_DEN"
            ]
        )

        for kind, label in (
            ("domestic", "Nội địa"),
            ("international", "Quốc tế")
        ):

            selected = yearly[
                yearly["LOAI"] == label
            ].copy()

            selected = (
                selected
                .sort_values(
                    "ASSENTOS",
                    ascending=False
                )
                .groupby(
                    "NAM",
                    group_keys=False
                )
                .head(100)
            )

            route_years[kind].append(
                selected.drop(columns="LOAI")
            )

        countries = (
            airports.set_index("CODE")["COUNTRY"]
            .to_dict()
        )

        origin_country = (
            allroutes["ORIGEM"].map(countries)
        )

        dest_country = (
            allroutes["DESTINO"].map(countries)
        )

        domestic_mask = (
            allroutes["LOAI"].eq("Nội địa")
            & origin_country.eq("BR")
            & dest_country.eq("BR")
        )

        international_mask = (
            allroutes["LOAI"].eq("Quốc tế")
            & origin_country.eq("BR")
            & dest_country.notna()
            & dest_country.ne("BR")
        )

        eligible = (
            domestic_mask | international_mask
        )

        newdest = (
            allroutes.loc[
                eligible.fillna(False)
            ]
            .groupby(
                ["THANG", "DESTINO", "LOAI"],
                as_index=False
            )["ASSENTOS"]
            .sum()
        )

        geo = airports.rename(columns={
            "CODE": "DESTINO",
            "NAME": "TEN_SAN_BAY",
            "CITY": "THANH_PHO",
            "COUNTRY": "QUOC_GIA"
        })

        newdest = newdest.merge(
            geo[
                [
                    "DESTINO", "TEN_SAN_BAY",
                    "THANH_PHO", "QUOC_GIA",
                    "LAT", "LON"
                ]
            ],
            on="DESTINO",
            how="left",
            validate="many_to_one"
        )

        newdest["DIA_DIEM"] = (
            newdest["THANH_PHO"]
            .fillna(newdest["TEN_SAN_BAY"])
            .fillna(newdest["DESTINO"])
        )

        destinations.append(newdest)

    month_out = (
        pd.concat(
            months,
            ignore_index=True
        )
        .sort_values(
            ["LOAI_CHUYEN_BAY", "THANG"]
        )
    )

    month_out = month_out.drop_duplicates(
        ["THANG", "LOAI_CHUYEN_BAY"],
        keep="first"
    )

    dest_out = pd.concat(
        destinations,
        ignore_index=True
    )

    dest_out = dest_out.drop_duplicates(
        ["THANG", "DESTINO", "LOAI"],
        keep="first"
    )

    for kind in ("domestic", "international"):

        routes = pd.concat(
            route_years[kind],
            ignore_index=True
        )

        routes = routes.drop_duplicates(
            ["NAM", "ORIGEM", "DESTINO"],
            keep="first"
        )

        save_csv(
            staged / OUTPUT[kind],
            routes
        )

    save_csv(
        staged / OUTPUT["month"],
        month_out
    )

    save_csv(
        staged / OUTPUT["dest"],
        dest_out
    )

    # Bao ve 24 dong du lieu thang cua 2024
    check_2024 = month_out[
        month_out["THANG"]
        .astype("string")
        .str.startswith("2024")
    ].copy()

    validate_2024(check_2024)

    keys = [
        "THANG",
        "LOAI_CHUYEN_BAY",
        "SO_GHE_BAN",
        "GIA_BINH_QUAN"
    ]

    original = (
        oldm[keys]
        .sort_values(
            ["THANG", "LOAI_CHUYEN_BAY"]
        )
        .reset_index(drop=True)
    )

    after = (
        check_2024[keys]
        .sort_values(
            ["THANG", "LOAI_CHUYEN_BAY"]
        )
        .reset_index(drop=True)
    )

    pd.testing.assert_frame_equal(
        original,
        after,
        check_dtype=False,
        check_exact=False,
        rtol=1e-9,
        atol=1e-9
    )

    return month_out


# ==================================================
# 9. CHUONG TRINH CHINH
# ==================================================

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--check",
        action="store_true"
    )

    parser.add_argument(
        "--recheck-all",
        action="store_true"
    )

    args = parser.parse_args()

    cfg = json.loads(
        CONFIG.read_text(
            encoding="utf-8"
        )
    )

    year_start = int(
        cfg.get("start_new_year", 2025)
    )

    if year_start < 2025:
        raise ValueError(
            "Nam cap nhat phai >= 2025"
        )

    sess = session()
    today = date.today()

    discoveries = {}
    errors = []

    for kind in ("domestic", "international"):

        for year in range(
            year_start,
            today.year + 1
        ):

            try:
                files = index_files(
                    sess, kind, year
                )

                for period, url in files.items():

                    if period > today.strftime("%Y-%m"):
                        continue

                    discoveries[
                        f"{kind}_{period}"
                    ] = url

                print(
                    f"{kind} {year}: "
                    f"tim thay {len(files)} thang"
                )

            except requests.exceptions.HTTPError as e:

                status = getattr(
                    e.response,
                    "status_code",
                    None
                )

                if status == 404:
                    print(
                        f"{kind} {year}: "
                        "chua co thu muc (404), bo qua"
                    )

                else:
                    msg = f"{kind} {year}: {e}"
                    errors.append(msg)
                    print("CANH BAO:", msg)

            except Exception as e:

                msg = f"{kind} {year}: {e}"
                errors.append(msg)
                print("CANH BAO:", msg)

    if args.check:

        for key, url in sorted(
            discoveries.items()
        ):
            print(key, url)

        print(
            "\nHOAN TAT KIEM TRA:",
            len(discoveries),
            "duong dan CSV."
        )

        if not discoveries:
            raise RuntimeError(
                "Khong tim thay nguon ANAC."
            )

        return

    if not discoveries:
        raise RuntimeError(
            "Khong tim duoc du lieu moi. "
            "Giu nguyen dashboard."
        )

    if STATE.exists():
        state = json.loads(
            STATE.read_text(encoding="utf-8")
        )
    else:
        state = {"months": {}}

    known = state.setdefault(
        "months", {}
    )

    pending = [
        (k, u)
        for k, u in sorted(discoveries.items())
        if k not in known
    ]

    recent_n = int(
        cfg.get("recheck_recent_months", 3)
    )

    recent_periods = sorted({
        k.split("_", 1)[1]
        for k in discoveries
    })[-recent_n:]

    for key, url in sorted(
        discoveries.items()
    ):

        if key in known and (
            args.recheck_all
            or key.split("_", 1)[1] in recent_periods
        ):
            pending.append((key, url))

    pending = list(
        dict(pending).items()
    )

    limit = int(
        cfg.get("max_files_per_run", 12)
    )

    pending = pending[
        :max(1, limit)
    ]

    if not pending:
        print(
            "Khong co du lieu moi. "
            "Dashboard giu nguyen."
        )
        return

    for filename in OUTPUT.values():

        if not (DATA / filename).exists():
            raise FileNotFoundError(
                f"Thieu file 2024: {filename}"
            )

    PARTS.mkdir(
        parents=True, exist_ok=True
    )

    with tempfile.TemporaryDirectory() as tmp:

        temp = Path(tmp)

        airports = load_airports(
            sess, cfg, temp
        )

        updates = []

        for key, url in pending:

            market, period = key.split(
                "_", 1
            )

            try:
                existing = PARTS / (
                    key + ".csv"
                )

                # Tai su dung bang thang da xu ly
                if (
                    key not in known
                    and existing.exists()
                    and not args.recheck_all
                ):

                    partial = read_csv(existing)

                    needed = {
                        "THANG", "LOAI",
                        "ORIGEM", "DESTINO",
                        "ASSENTOS",
                        "GIA_NHAN_GHE",
                        "GHE_CO_GIA"
                    }

                    if (
                        not partial.empty
                        and needed.issubset(partial.columns)
                        and set(
                            partial["THANG"].astype(str)
                        ) == {period}
                    ):

                        s_total = pd.to_numeric(
                            partial["ASSENTOS"],
                            errors="coerce"
                        ).sum()

                        f_total = pd.to_numeric(
                            partial["GIA_NHAN_GHE"],
                            errors="coerce"
                        ).sum()

                        w_total = pd.to_numeric(
                            partial["GHE_CO_GIA"],
                            errors="coerce"
                        ).sum()

                        if s_total > 0 and w_total > 0:

                            known[key] = {
                                "month": period,
                                "market": market,
                                "seats": float(s_total),
                                "fare_weight": float(f_total),
                                "fare_seats": float(w_total),
                                "rows": None,
                                "sha256": None,
                                "url": url
                            }

                            updates.append(key)

                            print(
                                "TAI SU DUNG DU LIEU:",
                                key
                            )

                            continue

                file = temp / (
                    key + ".csv"
                )

                digest = download(
                    sess, url, file
                )

                if (
                    key in known
                    and known[key].get("sha256") == digest
                ):
                    print(
                        "KHONG DOI:", key
                    )
                    continue

                routes, info = read_chunks(
                    file, period, market
                )

                save_csv(
                    PARTS / (key + ".csv"),
                    routes
                )

                known[key] = {
                    **info,
                    "sha256": digest,
                    "url": url
                }

                updates.append(key)

                print(
                    "DA XU LY:",
                    key,
                    "dong:", info["rows"],
                    "ghe:", int(info["seats"])
                )

            except Exception as e:

                msg = f"{key}: {e}"
                errors.append(msg)

                print(
                    "CANH BAO:", msg
                )

        if not updates:
            print(
                "Khong co tep moi duoc xu ly."
            )
            return

        BASELINE.mkdir(
            parents=True, exist_ok=True
        )

        for filename in OUTPUT.values():

            original = DATA / filename
            baseline = BASELINE / filename

            if not baseline.exists():
                shutil.copy2(
                    original, baseline
                )

        staged = temp / "out"
        staged.mkdir()

        result = build_combined(
            airports, state, staged
        )

        newstate = {
            "last_success_utc": (
                datetime.now(timezone.utc)
                .strftime("%Y-%m-%d %H:%M:%S")
            ),
            "period": (
                f"{result['THANG'].min()} "
                f"den {result['THANG'].max()}"
            ),
            "months": known,
            "newly_processed": updates,
            "warnings": errors,
            "year_coverage": sorted(
                result["THANG"]
                .str[:4]
                .unique()
                .tolist()
            ),
            "source": "ANAC Brazil / OurAirports"
        }

        status = staged / (
            "trang_thai_cap_nhat.json"
        )

        status.write_text(
            json.dumps(
                {
                    k: v for k, v in newstate.items()
                    if k != "months"
                },
                ensure_ascii=False,
                indent=2
            ) + "\n",
            encoding="utf-8"
        )

        for filename in OUTPUT.values():

            path = staged / filename

            if (
                not path.exists()
                or path.stat().st_size < 50
            ):
                raise ValueError(
                    f"Bang tong hop khong hop le: {filename}"
                )

        for filename in OUTPUT.values():

            (
                staged / filename
            ).replace(DATA / filename)

        status.replace(
            DATA / "trang_thai_cap_nhat.json"
        )

        STATE.write_text(
            json.dumps(
                newstate,
                ensure_ascii=False,
                indent=2
            ) + "\n",
            encoding="utf-8"
        )

        print()
        print("=" * 55)

        print(
            "CAP NHAT THANH CONG:",
            len(updates),
            "tep"
        )

        print(
            "CAC NAM:",
            newstate["year_coverage"]
        )

        print("=" * 55)

        if errors:
            print(
                "CANH BAO: Mot so nguon chua xu ly duoc."
            )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO
    )
    main()
