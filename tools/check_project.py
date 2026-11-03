from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
class Resources(HTMLParser):
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        key = "src" if tag in ("script","img") else "href" if tag == "link" else None
        value = a.get(key, "") if key else ""
        if value.startswith("./"):
            target = ROOT / "docs" / value[2:]
            assert target.is_file(), f"Risorsa assente: {value}"

Resources().feed((ROOT/"docs/index.html").read_text(encoding="utf-8"))
for ext in ("*.sqlite", "*.sqlite3", "*.db", "*.xls", "*.xlsx"):
    assert not list(ROOT.rglob(ext)), f"File operativo o database nel repository: {ext}"
assert not list((ROOT/"docs").rglob("*.csv")), "La demo pubblica non deve contenere CSV operativi."
print("Risorse presenti; nessun report operativo o database nel repository.")
