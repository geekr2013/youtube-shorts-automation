import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from ai_writer import GeminiWriter
from models import KnowledgeSource, ScriptPackage, TopicPlan
from quality import QualityGateError, validate_package
from run_status import build_status
from video_renderer import caption_timeline, split_caption_chunks


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.plan = TopicPlan(
            topic="생물발광의 원리",
            wiki_query="생물발광",
            stock_queries=["deep sea", "jellyfish", "ocean"],
        )
        hook = "깊은 바다의 생물은 왜 스스로 빛을 낼까요?"
        narration = (
            hook
            + " 생물발광은 생물의 몸속 화학 반응이 빛 에너지로 바뀌는 현상입니다. "
            "빛을 내는 물질과 효소가 산소와 반응하면서 열을 많이 만들지 않는 차가운 빛이 나타납니다. "
            "어두운 바다에서는 먹이를 유인하거나 포식자를 피하고, 같은 종끼리 신호를 보내는 데 쓰입니다. "
            "반딧불이와 일부 버섯도 비슷한 원리로 빛납니다. 결국 이 빛은 장식이 아니라 생존을 돕는 정교한 도구입니다."
        )
        self.script = ScriptPackage(
            title="깊은 바다 생물은 왜 스스로 빛날까",
            hook=hook,
            narration=narration,
            description_intro="생물발광의 원리와 쓰임을 설명합니다. 검증 자료를 바탕으로 구성했습니다.",
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

    def test_caption_chunks_stay_readable(self):
        chunks = split_caption_chunks(self.script.narration, max_chars=16)
        self.assertGreater(len(chunks), 5)
        self.assertTrue(all(len(chunk) <= 32 for chunk in chunks))
        timeline = caption_timeline(self.script.narration, 50.0)
        self.assertAlmostEqual(timeline[0][0], 0.0)
        self.assertAlmostEqual(timeline[-1][1], 50.0)

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


if __name__ == "__main__":
    unittest.main()

