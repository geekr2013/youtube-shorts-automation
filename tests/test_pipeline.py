import json
import re
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_writer import GeminiWriter, normalize_loop_ending, normalize_question_hook
from main import build_engagement_comment
from knowledge import _select_wikipedia_page
from models import KnowledgeSource, ScriptPackage, TopicPlan
from publish_preview import build_preview_description
from quality import QualityGateError, source_is_relevant, validate_package
from run_status import build_status
from secret_utils import clean_secret
from video_renderer import (
    BGM_MIX_VOLUME,
    BGM_TARGET_LUFS,
    background_music_frequencies,
    caption_font_size,
    caption_lines,
    caption_timeline,
    split_caption_chunks,
    write_ass,
)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.plan = TopicPlan(
            topic="생물발광의 원리",
            wiki_query="생물발광",
            stock_queries=["deep sea", "jellyfish", "ocean"],
        )
        hook = "깊은 바다의 생물은 왜 스스로 빛을 낼까요?"
        midpoint_hook = "그런데 같은 빛도 생물마다 쓰임이 다릅니다."
        closing_loop = "이 빛의 쓰임을 알고 처음 장면을 다시 보면…"
        narration = (
            hook
            + " 생물발광은 생물의 몸속 화학 반응이 빛 에너지로 바뀌는 현상입니다. "
            "빛을 내는 물질과 효소가 산소와 반응하면서 열을 많이 만들지 않는 차가운 빛이 나타납니다. "
            + midpoint_hook
            + " "
            "어두운 바다에서는 먹이를 유인하거나 포식자를 피하고, 같은 종끼리 신호를 보내는 데 쓰입니다. "
            "반딧불이와 일부 버섯도 비슷한 원리로 빛납니다. "
            + closing_loop
        )
        self.script = ScriptPackage(
            title="깊은 바다 생물은 왜 스스로 빛날까",
            hook=hook,
            narration=narration,
            description_intro="생물발광의 원리와 쓰임을 설명합니다. 검증 자료를 바탕으로 구성했습니다.",
            midpoint_hook=midpoint_hook,
            closing_loop=closing_loop,
            engagement_question="여러분이 직접 본 가장 신기한 빛은 무엇인가요?",
            tags=["생물발광", "심해", "과학", "자연", "지식"],
        )
        self.source = KnowledgeSource(
            title="생물발광",
            url="https://ko.wikipedia.org/wiki/example",
            extract="생물발광에 관한 검증 문장입니다. " * 30,
            language="ko",
        )

    def test_valid_package_passes(self):
        validate_package(self.plan, self.script, self.source, [])

    def test_duplicate_topic_is_blocked(self):
        with self.assertRaises(QualityGateError):
            validate_package(self.plan, self.script, self.source, ["생물 발광의 원리"])

    def test_midpoint_hook_must_be_near_the_middle(self):
        script = replace(self.script, midpoint_hook="대본에 없는 반전 문장입니다.")
        with self.assertRaises(QualityGateError):
            validate_package(self.plan, script, self.source, [])

    def test_hook_must_be_a_question(self):
        script = replace(self.script, hook="깊은 바다의 생물은 스스로 빛을 냅니다.")
        with self.assertRaises(QualityGateError):
            validate_package(self.plan, script, self.source, [])

    def test_non_question_ai_hook_is_normalized(self):
        narration, hook = normalize_question_hook(
            "벌집은 공간을 효율적으로 사용합니다. 그래서 육각형이 됩니다.",
            "벌집은 공간을 효율적으로 사용합니다.",
        )
        self.assertTrue(hook.endswith("?"))
        self.assertTrue(narration.startswith(hook))
        self.assertIn("벌집은 공간을 효율적으로 사용합니다.", narration)

    def test_unrelated_wikipedia_source_is_blocked(self):
        source = replace(
            self.source,
            title="버뮤다 삼각지대",
            extract="버뮤다 삼각지대에 관한 설명입니다. " * 30,
        )
        with self.assertRaises(QualityGateError):
            validate_package(self.plan, self.script, source, [])

    def test_related_source_can_match_topic_terms_in_extract(self):
        plan = replace(self.plan, topic="벌집이 육각형인 이유", wiki_query="벌집")
        source = replace(
            self.source,
            title="벌",
            extract="벌집은 육각형 구조로 만들어집니다. " * 30,
        )
        self.assertTrue(source_is_relevant(plan, source))

    def test_wikipedia_search_rank_beats_longest_article(self):
        selected = _select_wikipedia_page(
            [
                {"index": 2, "title": "긴 곁가지", "extract": "가" * 2000},
                {"index": 1, "title": "번개", "extract": "나" * 400},
            ]
        )
        self.assertEqual(selected[0]["title"], "번개")

    def test_closing_loop_must_end_the_narration(self):
        script = replace(self.script, closing_loop="다른 마지막 문장입니다.")
        with self.assertRaises(QualityGateError):
            validate_package(self.plan, script, self.source, [])

    def test_invalid_ai_loop_is_replaced_with_a_safe_loop(self):
        invalid = "이것이 생물발광의 놀라운 원리입니다."
        narration, closing = normalize_loop_ending(
            self.script.narration.replace(self.script.closing_loop, invalid),
            invalid,
        )
        self.assertEqual(closing, "이 사실을 알고 처음 장면을 다시 보면…")
        self.assertTrue(narration.endswith(closing))
        self.assertNotIn(invalid, narration)

    def test_engagement_question_is_ready_for_a_comment(self):
        comment = build_engagement_comment(self.script)
        self.assertIn(self.script.engagement_question, comment)
        self.assertIn("댓글", comment)

    def test_incidental_history_term_is_allowed_in_science_narration(self):
        script = replace(
            self.script,
            narration=self.script.narration.replace(
                "결국 이 빛은", "전쟁 시기에도 연구됐지만, 결국 이 빛은"
            ),
        )
        validate_package(self.plan, script, self.source, [])

    def test_caption_chunks_stay_readable(self):
        chunks = split_caption_chunks(self.script.narration)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(chunk) <= 22 or " " not in chunk for chunk in chunks))
        for chunk in chunks:
            lines = caption_lines(chunk)
            self.assertLessEqual(len(lines), 2)
            self.assertEqual(
                re.sub(r"\s", "", chunk),
                re.sub(r"\s", "", "".join(lines)),
            )
        timeline = caption_timeline(self.script.narration, 50.0)
        self.assertAlmostEqual(timeline[0][0], 0.0)
        self.assertAlmostEqual(timeline[-1][1], 50.0)

    def test_ass_has_no_top_brand_and_uses_safe_line_breaks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "captions.ass"
            write_ass(path, self.script.narration, 50.0)
            content = path.read_text(encoding="utf-8-sig")
        self.assertNotIn("오늘의 60초 호기심", content)
        self.assertIn(r"\N", content)
        self.assertIn("Noto Sans CJK KR,64", content)
        self.assertIn(r"\pos(450,1220)", content)
        self.assertIn(r"\fad(100,80)", content)
        self.assertRegex(content, r"\\fs\d+")

    def test_korean_word_is_never_split_between_caption_lines(self):
        lines = caption_lines("오로라가 선명하게 보이고 있습니다", max_line_chars=10)
        self.assertTrue(any("있습니다" in line for line in lines))
        self.assertFalse(any(line.endswith("있습니") for line in lines))
        self.assertEqual("오로라가 선명하게 보이고 있습니다", " ".join(lines))

    def test_long_caption_uses_smaller_font_without_splitting_words(self):
        short_size = caption_font_size(["빛이 납니다"])
        long_size = caption_font_size(["전자기적인 상호작용입니다"])
        self.assertLess(long_size, short_size)
        self.assertGreaterEqual(long_size, 50)

    def test_background_music_changes_with_topic_style(self):
        self.assertNotEqual(
            background_music_frequencies("과학"),
            background_music_frequencies("역사"),
        )
        self.assertEqual(BGM_TARGET_LUFS, -24.0)
        self.assertGreaterEqual(BGM_MIX_VOLUME, 1.0)

    def test_gemini_json_parser_accepts_code_fence(self):
        value = GeminiWriter._parse_json('```json\n{"topic":"구름"}\n```')
        self.assertEqual(value, {"topic": "구름"})

    def test_gemini_interaction_text_is_extracted(self):
        value = GeminiWriter._extract_interaction_text(
            {
                "steps": [
                    {"type": "user_input", "content": []},
                    {
                        "type": "model_output",
                        "content": [{"type": "text", "text": '{"topic":"번개"}'}],
                    },
                ]
            }
        )
        self.assertEqual(value, '{"topic":"번개"}')

    def test_github_models_text_is_extracted(self):
        value = GeminiWriter._extract_chat_text(
            {"choices": [{"message": {"content": '{"topic":"오로라"}'}}]}
        )
        self.assertEqual(value, '{"topic":"오로라"}')

    def test_github_models_schema_rejects_extra_fields(self):
        value = GeminiWriter._strict_schema(
            {"type": "object", "properties": {"topic": {"type": "string"}}}
        )
        self.assertFalse(value["additionalProperties"])

    def test_push_event_is_recorded_as_dry_run(self):
        value = build_status(
            {
                "RUN_EVENT": "push",
                "DRY_RUN_OUTCOME": "success",
                "UPLOAD_OUTCOME": "skipped",
                "RUN_ID": "123",
            }
        )
        self.assertEqual(value["mode"], "dry-run")
        self.assertEqual(value["outcome"], "success")

    def test_launch_push_is_recorded_as_upload(self):
        value = build_status(
            {
                "RUN_EVENT": "push",
                "DRY_RUN_OUTCOME": "skipped",
                "UPLOAD_OUTCOME": "success",
                "RUN_ID": "456",
            }
        )
        self.assertEqual(value["mode"], "upload")
        self.assertEqual(value["outcome"], "success")

    def test_preview_upload_is_recorded_as_upload(self):
        value = build_status(
            {
                "RUN_EVENT": "push",
                "DRY_RUN_OUTCOME": "skipped",
                "UPLOAD_OUTCOME": "skipped",
                "PREVIEW_UPLOAD_OUTCOME": "success",
                "RUN_ID": "789",
            }
        )
        self.assertEqual(value["mode"], "upload")
        self.assertEqual(value["outcome"], "success")

    def test_preview_description_includes_source_and_question(self):
        value = build_preview_description(
            {
                "title": "오로라가 생기는 과정",
                "source": {
                    "title": "오로라",
                    "url": "https://ko.wikipedia.org/wiki/오로라",
                    "license": "CC BY-SA 4.0",
                },
                "stock_assets": [],
                "engagement_comment": "가장 아름다운 하늘빛은 무엇이었나요?",
                "tags": ["오로라", "과학"],
            }
        )
        self.assertIn("https://ko.wikipedia.org/wiki/오로라", value)
        self.assertIn("가장 아름다운 하늘빛", value)

    def test_youtube_secret_format_is_cleaned(self):
        self.assertEqual(
            clean_secret('  YOUTUBE_CLIENT_SECRET="GOCSPX-example"  '),
            "GOCSPX-example",
        )


if __name__ == "__main__":
    unittest.main()

