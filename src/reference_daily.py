"""Daily mean air temperature of every Freiburg street-level station in a year,
streamed from the published file without keeping a copy of it.

usage: python src/reference_daily.py URL MD5 YEAR OUT.csv

URL is the Zenodo file of hourly values (columns datetime, station_id, ta,
type, ...; datetime in UTC; type is `measured`, or `predicted` for an hour
the curators gap-filled). The whole file is streamed so that its MD5 can be
checked against MD5, the checksum Zenodo publishes for it; only the hours of
YEAR are kept, summed per UTC day and station. Nothing is written unless the
checksum matches.

Each row of OUT: date (UTC), station, ta_mean_c (mean of the day's hourly
values, measured and gap-filled alike), n_hours, and n_measured (hours
of type `measured`).
"""

from __future__ import annotations

import csv
import hashlib
import http.client
import io
import os
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import UTC, datetime


class _Hashing(io.RawIOBase):
    """A readable stream that hashes every byte read through it."""

    def __init__(self, raw, digest):
        self._raw, self._digest = raw, digest

    def readable(self):
        return True

    def readinto(self, buffer):
        n = self._raw.readinto(buffer)
        if n:
            self._digest.update(memoryview(buffer)[:n])
        return n


def read_days(url: str, year: int) -> tuple[dict, str]:
    """Stream *url* once: the per-day sums of *year*, and the file's MD5."""
    digest = hashlib.md5()
    acc: dict[tuple[str, str], list] = defaultdict(lambda: [0.0, 0, 0])
    request = urllib.request.Request(url, headers={"User-Agent": "drift-study"})
    with urllib.request.urlopen(request, timeout=120) as response:
        stream = io.BufferedReader(_Hashing(response, digest), 1 << 20)
        rows = csv.reader(io.TextIOWrapper(stream, encoding="utf-8", newline=""))
        header = next(rows)
        i_time, i_station = header.index("datetime"), header.index("station_id")
        i_ta, i_type = header.index("ta"), header.index("type")
        for row in rows:
            when = datetime.fromisoformat(row[i_time])
            if when.tzinfo is None:
                raise ValueError(f"timestamp without a time zone: {row[i_time]!r}")
            when = when.astimezone(UTC)
            if when.year != year:
                continue
            if row[i_type] not in ("measured", "predicted"):
                raise ValueError(f"unknown type {row[i_type]!r} at {row[i_time]}")
            day = acc[(when.date().isoformat(), row[i_station])]
            day[0] += float(row[i_ta])
            day[1] += 1
            day[2] += row[i_type] == "measured"
    return acc, digest.hexdigest()


def main(url: str, md5: str, year: str, out: str, attempts: int = 4) -> None:
    for attempt in range(1, attempts + 1):
        try:
            acc, got = read_days(url, int(year))
            break
        except (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError) as error:
            # A server error or a dropped connection: stream it again, from the start.
            if isinstance(error, urllib.error.HTTPError) and error.code < 500:
                raise
            if attempt == attempts:
                raise
            print(f"attempt {attempt}: {error}; retrying", file=sys.stderr)
            time.sleep(15 * attempt)
    if got != md5:
        raise SystemExit(f"MD5 {got} of {url} is not the published {md5}")
    if not acc:
        raise SystemExit(f"no hours of {year} in {url}")

    partial = out + ".partial"
    with open(partial, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "station", "ta_mean_c", "n_hours", "n_measured"])
        for (date, station), (total, n, measured) in sorted(acc.items()):
            writer.writerow([date, station, f"{total / n:.6f}", n, measured])
    os.replace(partial, out)


if __name__ == "__main__":
    main(*sys.argv[1:])
