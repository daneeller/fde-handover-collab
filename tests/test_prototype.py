"""可运行原型的独立测试：python -m unittest discover -s tests -v"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.audit import build_audit  # noqa: E402
from src.locator import load_parts, locate  # noqa: E402
from src.main import load_defects  # noqa: E402
from src.prompts import render_location_prompt, render_redline_prompt  # noqa: E402
from src.rules import dedupe_by_master, detect_red_lines, handover_complete  # noqa: E402

DATA = ROOT / "src" / "data"


class PrototypeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.defects = load_defects()
        cls.parts = load_parts(DATA / "unit_parts.json")
        cls.by_id = {d.defect_id: d for d in cls.defects}

    def test_01_sample_data_shape(self):
        self.assertEqual(len(self.defects), 6)
        self.assertTrue(all(d.master_id for d in self.defects))

    def test_02_dedupe_by_master(self):
        masters, counts = dedupe_by_master(self.defects)
        self.assertEqual(len(masters), 6)
        self.assertEqual(sum(counts.values()), 7)
        self.assertEqual(counts["BU-20261101-005"], 2, "一缺陷多工单应计数为 2（f31）")

    def test_03_red_line_r1_unverified_close(self):
        codes = [x.code for x in detect_red_lines(self.by_id["D-1003"])]
        self.assertIn("R1", codes)

    def test_04_red_line_r2_r3(self):
        codes = [x.code for x in detect_red_lines(self.by_id["D-1005"])]
        self.assertIn("R2", codes)
        self.assertIn("R3", codes)

    def test_05_red_line_r4(self):
        codes = [x.code for x in detect_red_lines(self.by_id["D-1006"])]
        self.assertIn("R4", codes)

    def test_06_no_red_line_for_clean_record(self):
        self.assertEqual(detect_red_lines(self.by_id["D-1001"]), [])

    def test_07_location_hits_expected_part(self):
        for did in ("D-1001", "D-1002", "D-1003"):
            d = self.by_id[did]
            s = locate(d, self.parts)
            self.assertEqual(s["part_code"], d.expected_part, did)
            self.assertTrue(s["needs_confirmation"])

    def test_08_photo_description_conflict(self):
        s = locate(self.by_id["D-1004"], self.parts)
        self.assertTrue(s["photo_description_mismatch"])
        self.assertTrue(s["needs_confirmation"])

    def test_09_handover_needs_receiver_confirmation(self):
        self.assertTrue(handover_complete(self.by_id["D-1001"]))
        self.assertFalse(handover_complete(self.by_id["D-1005"]), "仅发消息不算完成（f23）")

    def test_10_audit_six_fields(self):
        d = self.by_id["D-1001"]
        rec = build_audit(d, locate(d, self.parts), detect_red_lines(d))
        for key in ("业务编号", "资料版本", "事实引用", "建议结果", "人工改动", "签核人"):
            self.assertIn(key, rec)
        self.assertEqual(rec["签核人"], "待人工填写")
        self.assertIn("f45", rec["事实引用"])

    def test_11_prompt_contains_provenance(self):
        d = self.by_id["D-1001"]
        p = render_location_prompt(d, self.parts)
        self.assertIn("f10", p)
        self.assertIn("待验证", p)
        self.assertIn("不关单", p)
        rp = render_redline_prompt(d)
        self.assertIn("R1", rp)
        self.assertIn("接手人", rp)

    def test_12_prompt_mode_never_executes(self):
        d = self.by_id["D-1003"]
        s = locate(d, self.parts, mode="prompt")
        self.assertEqual(s["mode"], "prompt")
        self.assertIn("prompt", s)
        self.assertNotIn("part_code", s)


if __name__ == "__main__":
    unittest.main(verbosity=2)
