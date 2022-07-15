#!/usr/bin/env python

import getpass
import math
import os.path
from pathlib import Path
import sys
import time
import urllib.parse

from bs4 import BeautifulSoup

import requests

import click


@click.command()
@click.option("-u", "--username", required=True)
@click.option("-p", "--password")
@click.option("--contains", help="Manga is required to contain this")
@click.argument("urls", nargs=-1)
def cli(username, password, contains, urls):
    if password == "-":
        password = sys.stdin.read().strip()
    elif password is None:
        password = getpass.getpass(f"Password for {username}: ")

    errored = False

    with requests.Session() as session:
        session.headers.update({"User-Agent": "Mozilla/5.0"})
        session.auth = (username, password)

        for url in urls:
            errored = dl_manga(session, url, contains) or errored

    if errored:
        sys.exit(1)


def dl_manga(session, url, contains):
    errored = False

    response = session.get(url)
    if response.status_code != 200:
        print("Login Error", file=sys.stderr)
        return

    soup = BeautifulSoup(response.content, "lxml")
    manga_info = soup.select_one("div.manga-info")
    if manga_info is None:
        # We are in a subdirectory
        parts = urllib.parse.urlparse(url)
        parts = parts._replace(path=os.path.dirname(parts.path))
        root_url = urllib.parse.urlunparse(parts)
        print(root_url)
        root_soup = BeautifulSoup(session.get(root_url).content, "lxml")
        manga_info = root_soup.select_one("div.manga-info")

    title = manga_info.select_one("span.title").get_text(strip=True)
    outdir = Path(title)
    outdir.mkdir(exist_ok=True)

    for row in soup.select("table#index-table tbody tr"):
        entry = row.select_one("td a")
        fname = entry.get_text(strip=True)
        fpath = outdir.joinpath(fname)
        entry_url = urllib.parse.urljoin(url, entry["href"])

        if contains is not None and contains not in fname:
            continue

        if fpath.exists():
            print(
                "Downloading {} ... Already downloaded".format(fname),
                flush=True,
            )
            continue
        prefix = "Downloading {} ... ".format(fname)
        try:
            requests_dl_file_progress(entry_url, fpath, session, prefix)
        except Exception as e:
            print(
                "WARNING: Failed to download {} ({})".format(entry_url, fname),
                flush=True,
            )
            errored = True

        time.sleep(0.1)

    return errored


def requests_dl_file_progress(url, path, session=None, prefix=""):
    if session is None:
        session = requests

    tmp_path = path.parent.joinpath(f"{path.name}.part")

    r = session.get(url, stream=True)

    if not r.headers.get("content-length"):
        raise Exception("No content-length")

    total_size = int(r.headers.get("content-length"))
    dl_size = 0

    start_time = time.time()
    last_flush_time = start_time
    with open(tmp_path, "wb") as f:
        for chunk in r.iter_content(1024 * 16):
            f.write(chunk)
            dl_size += len(chunk)
            time_elapsed = time.time() - start_time
            sys.stdout.write(
                "\r"
                + prefix
                + "({:4d}MB/{:4d}MB) {:3d}% {:.2f} KB/s ".format(
                    int(dl_size / 1e6),
                    math.ceil(total_size / 1e6),
                    int(dl_size * 100 / total_size),
                    dl_size / 1000 / time_elapsed,
                )
            )
            sys.stdout.flush()

    tmp_path.rename(path)

    time_elapsed = time.time() - start_time
    print(
        "\r"
        + prefix
        + "({:4d}MB/{:4d}MB) 100% {:.2f} KB/s ({}s taken)".format(
            math.ceil(total_size / 1e6),
            math.ceil(total_size / 1e6),
            dl_size / 1000 / time_elapsed,
            int(time_elapsed),
        )
    )


if __name__ == "__main__":
    cli()
