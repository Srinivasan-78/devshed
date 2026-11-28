import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import convert  # noqa: E402


def test_output_path_for_disambiguates_multiple_collisions(tmp_path):
    cfg = convert.Config(
        patterns=[],
        output_dir=tmp_path,
        ocr="auto",
        ocr_lang="eng",
        ocr_dpi=200,
        min_chars_per_page=100,
        max_file_bytes=0,
        compact=True,
        merge_into="",
        fail_on_error=False,
    )
    used: set[Path] = set()
    p1 = convert.output_path_for(Path("report.pdf"), cfg, used)
    p2 = convert.output_path_for(Path("report.docx"), cfg, used)
    p3 = convert.output_path_for(Path("report.txt"), cfg, used)
    assert p1.name == "report.md"
    assert p2.name == "report-2.md"
    assert p3.name == "report-3.md"


def test_yaml_quote_escapes_newlines_and_quotes():
    quoted = convert.yaml_quote('a\\b"c\nd\re')
    assert quoted == '"a\\\\b\\"c\\nd\\re"'


def test_compact_markdown_and_strip_repeated_lines():
    pages = ["Header\nBody 1\nFooter", "Header\nBody 2\nFooter", "Header\nBody 3\nFooter"]
    stripped = convert.strip_repeated_lines(pages)
    assert all("Header" not in p and "Footer" not in p for p in stripped)
    assert convert.compact_markdown("a   \n\n\n\nb\n") == "a\n\nb\n"
