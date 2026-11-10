import importlib.util
import json
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("newpod_import", Path(__file__).resolve().parents[1] / "tools" / "newpod_import.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

HEADER = "TAGID;DataIngresso;DataUscita;CLIEID;Nome;Cognome;Pulito;Sporco\n"
SAMPLE = (HEADER + "DEMO001;02/06/2026;03/06/2026;10.001;Uno;Demo;1;1\n"
          "DEMO002;04/06/2026;;10.002;Due;Demo;0;1\n").encode("utf-8")

class NewPodImportTests(unittest.TestCase):
    def test_dates_cycles_and_flags_remain_distinct(self):
        stats, rows, issues, encoding = module.analyze(SAMPLE, "ospiti")
        self.assertEqual((stats["rows"], stats["entries"], stats["exits"], stats["paired"], stats["entry_only"]), (2, 2, 1, 1, 1))
        self.assertEqual(issues, [])
        self.assertEqual(rows[0][1]["CLIEID"], "10.001")

    def test_same_source_id_in_two_archives_never_collides(self):
        self.assertNotEqual(module.external_person_key("ospiti", "10.001"), module.external_person_key("divise", "10.001"))

    def test_repeated_import_is_idempotent_and_new_version_preserves_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, db = Path(tmp) / "input.csv", Path(tmp) / "private.sqlite3"
            source.write_bytes(SAMPLE)
            first = module.stage_file(source, "ospiti", db)
            second = module.stage_file(source, "ospiti", db)
            self.assertFalse(first["already_imported"])
            self.assertTrue(second["already_imported"])
            source.write_bytes(SAMPLE.replace(b"03/06/2026", b"05/06/2026"))
            third = module.stage_file(source, "ospiti", db)
            self.assertNotEqual(first["batch_id"], third["batch_id"])
            with closing(sqlite3.connect(db)) as con:
                self.assertEqual(con.execute("SELECT count(*) FROM source_records").fetchone()[0], 4)
                original = json.loads(con.execute("SELECT raw_json FROM source_records WHERE batch_id=? ORDER BY source_row", (first["batch_id"],)).fetchone()[0])
                self.assertEqual(original["DataUscita"], "03/06/2026")

    def test_archives_stay_separate_in_database(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, db = Path(tmp) / "input.csv", Path(tmp) / "private.sqlite3"
            source.write_bytes(SAMPLE)
            module.stage_file(source, "ospiti", db)
            module.stage_file(source, "divise", db)
            with closing(sqlite3.connect(db)) as con:
                keys = {r[0] for r in con.execute("SELECT source_person_id FROM source_records")}
            self.assertIn("ospiti::10.001", keys)
            self.assertIn("divise::10.001", keys)

    def test_invalid_dates_and_inconsistent_flags_are_reported(self):
        raw = (HEADER + "DEMO001;31/02/2026;;10.001;Uno;Demo;0;0\n").encode()
        stats = module.analyze(raw, "ospiti")[0]
        self.assertEqual(stats["issues"]["invalid_date"], 1)
        self.assertEqual(stats["issues"]["flags"], 1)
        self.assertEqual(stats["entries"], 0)

    def test_report_footers_are_not_people(self):
        raw = ("Tit.;Cognome;Nome;Area;Ingresso\n.;Demo;Uno;A; 01-gen-2026\n1;0;;;\n1;;;;\nLavanderia;Elenco ospiti;Pagina 1;;\n").encode()
        result = module.analyze(raw, "ospiti")[0]
        self.assertEqual(result["rows"], 1)

    def test_windows_1252_and_quoted_semicolons(self):
        raw = ("Tit.;Cognome;Nome;Area;Ingresso\n.;Demo;Andr\xe9;\"Area; A\"; 01-gen-2026\n").encode("cp1252")
        _, rows, encoding, _ = module.parse_report(raw)
        self.assertEqual(encoding, "windows-1252")
        self.assertEqual(rows[0][1]["Nome"], "Andr\xe9")
        self.assertEqual(rows[0][1]["Area"], "Area; A")

    def test_source_rows_and_duplicate_rows_are_preserved(self):
        line = "DEMO001;02/06/2026;03/06/2026;10.001;Uno;Demo;1;1\n"
        stats, rows, issues, _ = module.analyze((HEADER + line + line).encode(), "ospiti")
        self.assertEqual(len(rows), 2)
        self.assertEqual(stats["issues"]["duplicate_row"], 1)
        self.assertEqual(rows[0][0], 2)
        self.assertEqual(rows[1][0], 3)

    def test_numeric_tag_is_not_a_report_footer(self):
        raw = b"TAGID;DataIngresso;DataUscita\n00001234;02/06/2026;\n"
        _, rows, _, _ = module.parse_report(raw)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1]["TAGID"], "00001234")

if __name__ == "__main__":
    unittest.main()
