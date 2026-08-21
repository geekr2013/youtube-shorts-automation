import base64
import re
import sys
import tempfile
import unittest
import wave
from dataclasses import replace
from datetime import date
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from main import build_description, build_engagement_comment
from pilates_catalog import (
    EXERCISES,
    INSTRUCTOR_ID,
    ROUTINES,
    build_narration,
    routine_exercises,
    select_routine,
    validate_routine,
)
from pilates_renderer import (
    AUDIO_MIX_MODE,
    EDGE_TTS_VOICES,
    GEMINI_TTS_MODEL,
    GEMINI_TTS_VOICE,
    MOTION_MODE,
    REFERENCE_IMAGE,
    _synthesize_gemini_tts,
    narration_audio_filter,
    prepare_narration_text,
    segment_plan,
    write_overlay_ass,
)
from publish_preview import build_preview_description
from run_status import build_status
from secret_utils import clean_secret


class PilatesPipelineTests(unittest.TestCase):
    def setUp(self):
        self.routine = ROUTINES[0]

    def test_instructor_identity_is_locked(self):
        self.assertEqual(INSTRUCTOR_ID, "hana-v1")
        reference = REFERENCE_IMAGE
        self.assertTrue(reference.exists())
        self.assertGreater(reference.stat().st_size, 500_000)
        self.assertEqual(reference.name, "hana-alignment-reference.png")

    def test_catalog_has_long_term_rotation(self):
        self.assertGreaterEqual(len(ROUTINES), 10)
        self.assertEqual(len({item.routine_id for item in ROUTINES}), len(ROUTINES))
        for routine in ROUTINES:
            self.assertEqual(len(routine.exercise_slugs), 3)
            self.assertEqual(len(set(routine.exercise_slugs)), 3)

    def test_every_exercise_has_a_reviewed_pose_asset(self):
        self.assertGreaterEqual(len(EXERCISES), 7)
        for exercise in EXERCISES.values():
            self.assertTrue(exercise.pose_path.exists(), exercise.pose_path)
            self.assertGreater(exercise.pose_path.stat().st_size, 100_000)
            self.assertIn(exercise.pose_path.suffix, {".jpg", ".png"})

    def test_every_exercise_has_reviewed_motion_keyframes(self):
        angles = set()
        for exercise in EXERCISES.values():
            for path in (exercise.motion_start_path, exercise.motion_end_path):
                self.assertTrue(path.exists(), path)
                self.assertGreater(path.stat().st_size, 500_000)
                self.assertEqual(path.suffix, ".png")
            self.assertTrue(exercise.muscle_focus)
            angles.add(exercise.camera_angle)
        self.assertIn("overhead", angles)
        self.assertIn("side-three-quarter", angles)
        self.assertIn("front-alignment", angles)
        self.assertEqual(MOTION_MODE, "reviewed-keyframe-sequence")

    def test_catalog_covers_chest_glutes_and_inner_thighs(self):
        self.assertIn("가슴", EXERCISES["kneeling-push-up"].muscle_focus)
        self.assertIn("둔근", EXERCISES["glute-bridge"].muscle_focus)
        self.assertIn("내전근", EXERCISES["inner-thigh-lift"].muscle_focus)
        self.assertEqual(EXERCISES["dead-bug"].camera_angle, "overhead")

    def test_every_exercise_has_korean_and_english_guidance(self):
        for exercise in EXERCISES.values():
            self.assertTrue(exercise.name_ko)
            self.assertRegex(exercise.name_en, r"^[A-Z0-9 &-]+$")
            self.assertTrue(exercise.cue_ko)
            self.assertRegex(exercise.cue_en, r"^[A-Z0-9 &-]+$")
            self.assertTrue(exercise.prescription_ko)
            self.assertTrue(exercise.prescription_en)

    def test_narration_uses_native_korean_count_words(self):
        for routine in ROUTINES:
            narration = build_narration(routine)
            self.assertFalse(any(character.isdigit() for character in narration))
            self.assertRegex(narration, r"(다섯|여섯|여덟|스무)")

    def test_routine_validator_blocks_medical_claims(self):
        unsafe = replace(self.routine, intro_ko="통증 치료를 위한 세 동작입니다.")
        with self.assertRaises(ValueError):
            validate_routine(unsafe)

    def test_recent_routines_are_not_immediately_repeated(self):
        records = [{"routine_id": item.routine_id} for item in ROUTINES[:5]]
        selected = select_routine(records, today=date(2026, 8, 19))
        self.assertNotIn(selected.routine_id, {item.routine_id for item in ROUTINES[:5]})

    def test_routine_selection_is_stable_for_the_same_day(self):
        first = select_routine([], today=date(2026, 8, 19))
        second = select_routine([], today=date(2026, 8, 19))
        self.assertEqual(first.routine_id, second.routine_id)

    def test_segment_plan_starts_with_three_readable_movement_sections(self):
        lengths = segment_plan(32.0)
        self.assertEqual(len(lengths), 3)
        self.assertAlmostEqual(sum(lengths), 32.0)
        self.assertTrue(all(item >= 5.5 for item in lengths))

    def test_overlay_is_bilingual_and_inside_shorts_safe_area(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "captions.ass"
            metadata = write_overlay_ass(path, self.routine, 32.0)
            content = path.read_text(encoding="utf-8-sig")
        first = routine_exercises(self.routine)[0]
        self.assertIn(first.name_ko, content)
        self.assertIn(first.name_en, content)
        self.assertIn(first.cue_ko, content)
        self.assertIn(first.cue_en, content)
        self.assertIn(r"\pos(48,120)", content)
        self.assertIn(r"\pos(82,160)", content)
        self.assertIn("NanumGothic", content)
        self.assertNotRegex(content, r"\\pos\([^,]+,1[5-9]\d{2}\)")
        self.assertEqual(metadata["language_mode"], "ko+en")
        self.assertIn("no automatic Korean syllable splitting", metadata["wrap_mode"])
        self.assertIn("movement starts on frame one", metadata["hook"])
        self.assertIn("movement_visibility", metadata)

    def test_voice_is_young_female_and_voice_only(self):
        self.assertEqual(GEMINI_TTS_MODEL, "gemini-3.1-flash-tts-preview")
        self.assertEqual(GEMINI_TTS_VOICE, "Aoede")
        self.assertEqual(EDGE_TTS_VOICES[0], "ko-KR-SunHiNeural")
        self.assertEqual(AUDIO_MIX_MODE, "voice_only")

    def test_gemini_tts_prompt_requires_natural_female_instruction(self):
        pcm = b"\x00\x00" * 240
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "voice.wav"
            with patch("pilates_renderer.requests.post", create=True) as request:
                request.return_value.raise_for_status.return_value = None
                request.return_value.json.return_value = {
                    "candidates": [{"content": {"parts": [{"inlineData": {
                        "data": base64.b64encode(pcm).decode("ascii"),
                        "mimeType": "audio/L16;codec=pcm;rate=24000",
                    }}]}}]
                }
                _synthesize_gemini_tts("다섯 번 반복해요.", output, "secret-value")
            _, kwargs = request.call_args
            prompt_text = kwargs["json"]["contents"][0]["parts"][0]["text"]
            self.assertIn("이십 대 한국인 여성 필라테스 강사", prompt_text)
            self.assertIn("한글로 적힌 숫자", prompt_text)
            self.assertNotIn("params", kwargs)
            with wave.open(str(output), "rb") as audio_file:
                self.assertEqual(audio_file.getframerate(), 24000)

    def test_narration_pacing_is_sentence_aware(self):
        prepared = prepare_narration_text("첫 동작입니다. 천천히 움직여요.")
        self.assertEqual(prepared, "첫 동작입니다.\n천천히 움직여요.")
        self.assertIn("loudnorm=I=-16", narration_audio_filter(32.0))

    def test_description_discloses_virtual_adult_and_safety(self):
        description = build_description(self.routine)
        self.assertIn("AI로 만든 가상 성인 강사", description)
        self.assertIn("실제 인물이 아닙니다", description)
        self.assertIn("통증", description)
        self.assertIn("#Pilates", description)

    def test_comment_uses_routine_question(self):
        comment = build_engagement_comment(self.routine)
        self.assertIn(self.routine.engagement_question, comment)

    def test_preview_description_matches_pilates_format(self):
        exercise = routine_exercises(self.routine)[0]
        value = build_preview_description({
            "content_format": "pilates-hana-motion-v3",
            "title": "아침 코어",
            "exercises": [{
                "name_ko": exercise.name_ko,
                "name_en": exercise.name_en,
                "prescription_ko": exercise.prescription_ko,
            }],
            "engagement_comment": "어느 동작이 어려웠나요?",
        })
        self.assertIn("가상 성인 강사", value)
        self.assertIn(exercise.name_en, value)
        self.assertIn("#필라테스", value)

    def test_main_no_longer_uses_stock_or_documentary_pipeline(self):
        source = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
        self.assertNotIn("StockMediaProvider", source)
        self.assertNotIn("research_exact_topic", source)
        self.assertNotIn("GeminiWriter", source)

    def test_renderer_compresses_skin_highlights(self):
        source = (ROOT / "src" / "pilates_renderer.py").read_text(encoding="utf-8")
        self.assertIn("colorlevels=romax=0.95", source)
        self.assertIn("diffused matte skin", source)

    def test_renderer_reencodes_all_three_motion_segments(self):
        source = (ROOT / "src" / "pilates_renderer.py").read_text(encoding="utf-8")
        self.assertIn("[v0][v1][v2]concat=n=3:v=1:a=0[outv]", source)
        self.assertIn("blend=all_expr", source)
        self.assertNotIn('str(concat_file)', source)

    def test_upload_declares_synthetic_media(self):
        source = (ROOT / "src" / "youtube_uploader.py").read_text(encoding="utf-8")
        self.assertIn('"containsSyntheticMedia": True', source)
        self.assertIn('category_id: str = "26"', source)

    def test_workflow_keeps_daily_public_schedule_and_tracks_assets(self):
        source = (ROOT / ".github" / "workflows" / "daily-upload.yml").read_text(encoding="utf-8")
        self.assertIn("Daily Hana Pilates Short", source)
        self.assertIn("cron: '35 10 * * *'", source)
        self.assertIn("assets/instructor/**", source)
        self.assertIn("YOUTUBE_PRIVACY: public", source)

    def test_push_event_is_recorded_as_dry_run(self):
        value = build_status({
            "RUN_EVENT": "push",
            "DRY_RUN_OUTCOME": "success",
            "UPLOAD_OUTCOME": "skipped",
            "RUN_ID": "123",
        })
        self.assertEqual(value["mode"], "dry-run")
        self.assertEqual(value["outcome"], "success")

    def test_youtube_secret_format_is_cleaned(self):
        self.assertEqual(clean_secret('  YOUTUBE_CLIENT_SECRET="GOCSPX-example"  '), "GOCSPX-example")


if __name__ == "__main__":
    unittest.main()
