"""Anki apkg export engine - generate Anki-compatible flashcard decks"""
import sqlite3
import zipfile
import uuid
import json
import tempfile
import shutil
from datetime import datetime, timezone
from pathlib import Path
from app.config import settings


def export_apkg(cards: list[dict], deck_name: str, output_path: str | None = None) -> str:
    """Export a list of flashcards to an Anki .apkg file.

    Args:
        cards: list of dicts with {front, back, card_type, tags}
        deck_name: name of the Anki deck
        output_path: optional output file path

    Returns:
        Path to the generated .apkg file
    """
    if not output_path:
        export_dir = Path(settings.export_dir) / "anki_cards"
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(export_dir / f"{deck_name}_{timestamp}.apkg")

    # Build SQLite database in a temp file (avoids serialize() compatibility issues)
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = Path(tmp_dir) / "collection.anki2"
        conn = sqlite3.connect(str(db_path))

        _create_anki_schema(conn)
        _populate_anki_data(conn, cards, deck_name)
        conn.close()

        # Write to zip (apkg is a zip of collection.anki2 + media)
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.write(str(db_path), "collection.anki2")
            # Empty media file (required by Anki)
            zf.writestr("media", "{}")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    return output_path


def _create_anki_schema(conn: sqlite3.Connection):
    """Create minimal Anki collection schema."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS col (
            id INTEGER PRIMARY KEY,
            crt INTEGER NOT NULL,
            mod INTEGER NOT NULL,
            scm INTEGER NOT NULL,
            ver INTEGER NOT NULL,
            dty INTEGER NOT NULL,
            usn INTEGER NOT NULL,
            ls INTEGER NOT NULL,
            conf TEXT NOT NULL,
            models TEXT NOT NULL,
            decks TEXT NOT NULL,
            dconf TEXT NOT NULL,
            tags TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY,
            guid TEXT NOT NULL,
            mid INTEGER NOT NULL,
            mod INTEGER NOT NULL,
            usn INTEGER NOT NULL,
            tags TEXT NOT NULL,
            flds TEXT NOT NULL,
            sfld TEXT NOT NULL,
            csum INTEGER NOT NULL,
            flags INTEGER NOT NULL,
            data TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY,
            nid INTEGER NOT NULL,
            did INTEGER NOT NULL,
            ord INTEGER NOT NULL,
            mod INTEGER NOT NULL,
            usn INTEGER NOT NULL,
            type INTEGER NOT NULL,
            queue INTEGER NOT NULL,
            due INTEGER NOT NULL,
            ivl INTEGER NOT NULL,
            factor INTEGER NOT NULL,
            reps INTEGER NOT NULL,
            lapses INTEGER NOT NULL,
            left INTEGER NOT NULL,
            odue INTEGER NOT NULL,
            odid INTEGER NOT NULL,
            flags INTEGER NOT NULL,
            data TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS revlog (
            id INTEGER PRIMARY KEY,
            cid INTEGER NOT NULL,
            usn INTEGER NOT NULL,
            ease INTEGER NOT NULL,
            ivl INTEGER NOT NULL,
            lastIvl INTEGER NOT NULL,
            factor INTEGER NOT NULL,
            time INTEGER NOT NULL,
            type INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS graves (
            usn INTEGER NOT NULL,
            oid INTEGER NOT NULL,
            type INTEGER NOT NULL
        );
    """)


def _populate_anki_data(conn: sqlite3.Connection, cards: list[dict], deck_name: str):
    """Populate Anki collection with cards."""
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    deck_id = 1
    model_id = int(now / 1000)

    # Basic note model (front/back)
    models = {
        str(model_id): {
            "id": model_id,
            "name": "Basic",
            "type": 0,
            "mod": now,
            "usn": -1,
            "sortf": 0,
            "did": deck_id,
            "tmpls": [{
                "name": "Card 1",
                "ord": 0,
                "qfmt": "{{Front}}",
                "afmt": "{{FrontSide}}\n\n<hr id=answer>\n\n{{Back}}",
                "bqfmt": "", "bafmt": "", "did": None, "bfont": "", "bsize": 0,
            }],
            "flds": [
                {"name": "Front", "ord": 0, "rtl": False, "sticky": False, "font": "Arial", "size": 20},
                {"name": "Back", "ord": 1, "rtl": False, "sticky": False, "font": "Arial", "size": 20},
            ],
            "css": ".card { font-family: arial; font-size: 20px; text-align: center; color: black; background-color: white; }",
            "latexPre": "", "latexPost": "", "req": [[0, "all", [0]]],
        }
    }

    decks = {str(deck_id): {"id": deck_id, "name": deck_name, "mod": now, "usn": -1,
                              "desc": "", "collapsed": False, "browserCollapsed": False,
                              "conf": 1, "extendNew": 10, "extendRev": 50}}

    dconf = {"1": {"id": 1, "name": "Default", "new": {"delays": [1, 10], "ints": [1, 4, 7],
                "initialFactor": 2500, "order": 0, "perDay": 20, "bury": True},
        "lapse": {"delays": [10], "mult": 0, "minInt": 1, "leechFails": 8, "leechAction": 0},
        "rev": {"perDay": 200, "ease4": 1.3, "fuzz": 0.05, "minSpace": 1, "ivlFct": 1,
                "maxIvl": 36500, "bury": True, "hardFactor": 1.2}, "maxTaken": 60,
        "timer": 0, "autoplay": True, "replayq": True, "mod": 0, "usn": 0}}

    all_tags = set()
    for c in cards:
        all_tags.update(c.get("tags", []))

    col_data = {
        "crt": now, "mod": now, "scm": 0, "ver": 16, "dty": 0, "usn": -1,
        "ls": now, "conf": json.dumps({"activeDecks": [1], "curDeck": 1, "newSpread": 0,
            "collapseTime": 1200, "timeLim": 0, "estTimes": True, "dueCounts": True,
            "curModel": str(model_id), "nextPos": len(cards) + 1}),
        "models": json.dumps(models), "decks": json.dumps(decks),
        "dconf": json.dumps(dconf), "tags": json.dumps({t: 0 for t in all_tags}),
    }

    conn.execute(
        "INSERT INTO col (id, crt, mod, scm, ver, dty, usn, ls, conf, models, decks, dconf, tags) "
        "VALUES (1, :crt, :mod, :scm, :ver, :dty, :usn, :ls, :conf, :models, :decks, :dconf, :tags)",
        col_data,
    )

    for i, card in enumerate(cards):
        guid = str(uuid.uuid4())[:10]
        flds = f"{card.get('front', '')}\x1f{card.get('back', '')}"
        sfld = card.get("front", "")[:100]
        tags_str = " ".join(card.get("tags", []))

        conn.execute(
            "INSERT INTO notes (id, guid, mid, mod, usn, tags, flds, sfld, csum, flags, data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (i + 1, guid, model_id, now, -1, tags_str, flds, sfld, 0, 0, ""),
        )
        conn.execute(
            "INSERT INTO cards (id, nid, did, ord, mod, usn, type, queue, due, ivl, factor, reps, lapses, left, odue, odid, flags, data) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (i + 1, i + 1, deck_id, 0, now, -1, 0, 0, i, 0, 0, 0, 0, 0, 0, 0, 0, ""),
        )
