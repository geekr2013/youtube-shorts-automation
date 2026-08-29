import base64
import json
import re
import sys
import tempfile
import unittest
import wave
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from main import PUBLIC_TAGS, build_description, build_engagement_comment, build_title, check_configuration
from media_provider import MIN_FRAME_RATE, MIN_VIDEO_EDGE, StockMediaProvider
from model_candidate_review import parse_source_ids
from models import StockClip
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
    _natural_grade_filter,
    _synthesize_gemini_tts,
    narration_audio_filter,
    prepare_narration_text,
    segment_plan,
    write_overlay_ass,
)
from pilates_video_strategy import (
    EXERCISE_VIDEO_SEARCH,
    FIXED_CONTENT_FORMAT,
    FIXED_MODEL_CREATOR,
    FIXED_MODEL_ID,
    FIXED_MODEL_SOURCES,
    MUSCLE_CLOSEUP_Y,
    PREFERRED_SOURCE_IDS,
    REAL_VIDEO_ROUTINE_IDS,
    SOURCE_REQUIREMENTS,
    build_clip_queries,
    is_fixed_model_source,
    is_human_reviewed_source,
    real_video_routine_candidates,
)
from publish_preview import build_preview_description, resolve_preview_dir
from run_status import build_status
from secret_utils import clean_secret
from trend_scout import editing_profile, fetch_pilates_short_benchmarks
from youtube_uploader import YouTubeUploader
from visual_quality import (
    GEMINI_VISION_MODEL,
    GeminiVisualQualityGate,
    meets_visual_thresholds,
)


class PilatesPipelineTests(unittest.TestCase):
    def setUp(self):
        self.routine = ROUTINES[0]

    def test_model_candidate_ids_support_ranges_and_deduplicate(self):
        self.assertEqual(
            parse_source_ids("6437910-6437912, 6437911, 6452931"),
            ["6437910", "6437911", "6437912", "6452931"],
        )

    def test_model_candidate_ids_reject_invalid_ranges(self):
        with self.assertRaises(ValueError):
            parse_source_ids("6437912-6437910")

    def test_hana_is_the_voice_brand_while_visuals_are_real_people(self):
        self.assertEqual(INSTRUCTOR_ID, "hana-v1")
        description = build_description(self.routine)
        self.assertIn("HANA", description)
        self.assertIn("licensed Pexels footage", description)
        self.assertIn("same adult Pilates model", description)
        self.assertNotRegex(description, r"[가-힣ㄱ-ㅎㅏ-ㅣ]")

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

    def test_every_exercise_has_real_video_search_and_closeup_focus(self):
        angles = set()
        for exercise in EXERCISES.values():
            self.assertIn(exercise.slug, EXERCISE_VIDEO_SEARCH)
            self.assertIn("woman", EXERCISE_VIDEO_SEARCH[exercise.slug])
            self.assertIn(exercise.slug, MUSCLE_CLOSEUP_Y)
            self.assertGreaterEqual(MUSCLE_CLOSEUP_Y[exercise.slug], 0.3)
            self.assertLessEqual(MUSCLE_CLOSEUP_Y[exercise.slug], 0.75)
            self.assertTrue(exercise.muscle_focus)
            angles.add(exercise.camera_angle)
        self.assertIn("overhead", angles)
        self.assertIn("side-three-quarter", angles)
        self.assertIn("front-alignment", angles)
        self.assertEqual(MOTION_MODE, "licensed-real-video-with-form-closeups")
        self.assertIn("real continuous human movement", SOURCE_REQUIREMENTS)

    def test_catalog_covers_chest_glutes_and_inner_thighs(self):
        self.assertIn("가슴", EXERCISES["kneeling-push-up"].muscle_focus)
        self.assertIn("둔근", EXERCISES["glute-bridge"].muscle_focus)
        self.assertIn("내전근", EXERCISES["inner-thigh-lift"].muscle_focus)
        self.assertEqual(EXERCISES["dead-bug"].camera_angle, "overhead")

    def test_every_exercise_has_complete_english_public_guidance(self):
        for exercise in EXERCISES.values():
            self.assertRegex(exercise.name_en, r"^[A-Z0-9 &-]+$")
            self.assertRegex(exercise.cue_en, r"^[A-Z0-9 &-]+$")
            self.assertRegex(exercise.prescription_en, r"^\d+")

    def test_narration_is_english_only_with_natural_count_words(self):
        for routine in ROUTINES:
            narration = build_narration(routine)
            self.assertFalse(any(character.isdigit() for character in narration))
            self.assertNotRegex(narration, r"[가-힣ㄱ-ㅎㅏ-ㅣ]")
            self.assertIn("First", narration)
            self.assertIn("Next", narration)
            self.assertIn("Finally", narration)
            self.assertIn("stop if you feel pain", narration)

    def test_visible_english_prescriptions_use_digits_while_voice_uses_words(self):
        for exercise in EXERCISES.values():
            self.assertRegex(exercise.prescription_en, r"^\d+")
        narration = build_narration(next(item for item in ROUTINES if item.routine_id == "fixed-plank-transition"))
        self.assertIn("twenty seconds", narration)
        self.assertNotRegex(narration, r"\d")

    def test_routine_validator_blocks_medical_claims(self):
        unsafe = replace(self.routine, intro_ko="통증 치료를 위한 세 동작입니다.")
        with self.assertRaises(ValueError):
            validate_routine(unsafe)
        unsafe_english = replace(self.routine, title_en="CURE BACK PAIN")
        with self.assertRaises(ValueError):
            validate_routine(unsafe_english)

    def test_recent_routines_are_not_immediately_repeated(self):
        records = [{"routine_id": item.routine_id} for item in ROUTINES[:5]]
        selected = select_routine(records, today=date(2026, 8, 19))
        self.assertNotIn(selected.routine_id, {item.routine_id for item in ROUTINES[:5]})

    def test_real_video_candidates_avoid_hard_to_match_prop_routines(self):
        candidates = real_video_routine_candidates([], today=date(2026, 8, 21), limit=3)
        self.assertEqual(len(candidates), 3)
        self.assertTrue(all(item.routine_id in REAL_VIDEO_ROUTINE_IDS for item in candidates))
        self.assertTrue(all("ring-side-bend" not in item.exercise_slugs for item in candidates))
        self.assertTrue(all("side-leg-lift" not in item.exercise_slugs for item in candidates))
        self.assertTrue(all(slug in FIXED_MODEL_SOURCES for item in candidates for slug in item.exercise_slugs))

    def test_every_scheduled_routine_has_exact_human_reviewed_sources(self):
        by_id = {item.routine_id: item for item in ROUTINES}
        for routine_id in REAL_VIDEO_ROUTINE_IDS:
            for slug in by_id[routine_id].exercise_slugs:
                self.assertIn(slug, PREFERRED_SOURCE_IDS)
                source_id = PREFERRED_SOURCE_IDS[slug][0]
                self.assertEqual(source_id, FIXED_MODEL_SOURCES[slug])
                self.assertTrue(is_human_reviewed_source(slug, "Pexels", source_id))
                self.assertTrue(
                    is_fixed_model_source(slug, "Pexels", source_id, FIXED_MODEL_CREATOR)
                )
                self.assertFalse(is_human_reviewed_source(slug, "Pixabay", source_id))
                self.assertFalse(is_human_reviewed_source(slug, "Pexels", "unreviewed"))
                self.assertFalse(is_fixed_model_source(slug, "Pexels", source_id, "Other"))
        self.assertEqual(FIXED_MODEL_ID, "miriam-alonso-core-v1")

    def test_routine_selection_is_stable_for_the_same_day(self):
        first = select_routine([], today=date(2026, 8, 19))
        second = select_routine([], today=date(2026, 8, 19))
        self.assertEqual(first.routine_id, second.routine_id)

    def test_segment_plan_starts_with_three_readable_movement_sections(self):
        lengths = segment_plan(32.0)
        self.assertEqual(len(lengths), 3)
        self.assertAlmostEqual(sum(lengths), 32.0)
        self.assertTrue(all(item >= 5.5 for item in lengths))

    def test_overlay_is_english_only_premium_and_inside_shorts_safe_area(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "captions.ass"
            metadata = write_overlay_ass(path, self.routine, 32.0)
            content = path.read_text(encoding="utf-8-sig")
        first = routine_exercises(self.routine)[0]
        self.assertIn(first.name_en.title(), content)
        self.assertIn(first.cue_en.capitalize(), content)
        self.assertIn(first.prescription_en, content)
        self.assertNotIn(first.name_ko, content)
        self.assertNotIn(first.cue_ko, content)
        self.assertNotRegex(content, r"[가-힣ㄱ-ㅎㅏ-ㅣ]")
        self.assertIn(r"\pos(48,120)", content)
        self.assertIn(r"\pos(92,150)", content)
        self.assertIn("Style: Title,Lato,56", content)
        self.assertIn("Style: Cue,Lato,40", content)
        self.assertIn(r"\fad(180,140)", content)
        self.assertNotRegex(content, r"\\pos\([^,]+,1[5-9]\d{2}\)")
        self.assertEqual(metadata["language_mode"], "en")
        self.assertEqual(metadata["locale"], "en-US")
        self.assertEqual(metadata["font"], "Lato")
        self.assertIn("movement starts on frame one", metadata["hook"])
        self.assertIn("movement_visibility", metadata)

    def test_voice_is_young_female_and_voice_only(self):
        self.assertEqual(GEMINI_TTS_MODEL, "gemini-3.1-flash-tts-preview")
        self.assertEqual(GEMINI_TTS_VOICE, "Aoede")
        self.assertEqual(EDGE_TTS_VOICES[0], "en-US-AvaMultilingualNeural")
        self.assertTrue(all(voice.startswith("en-US-") for voice in EDGE_TTS_VOICES))
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
                _synthesize_gemini_tts("Complete five controlled repetitions.", output, "secret-value")
            _, kwargs = request.call_args
            prompt_text = kwargs["json"]["contents"][0]["parts"][0]["text"]
            self.assertIn("natural North American English", prompt_text)
            self.assertIn("neutral General American accent", prompt_text)
            self.assertIn("Do not rewrite", prompt_text)
            self.assertNotRegex(prompt_text, r"[가-힣ㄱ-ㅎㅏ-ㅣ]")
            self.assertNotIn("params", kwargs)
            with wave.open(str(output), "rb") as audio_file:
                self.assertEqual(audio_file.getframerate(), 24000)

    def test_narration_pacing_is_sentence_aware(self):
        prepared = prepare_narration_text("First movement. Move with control.")
        self.assertEqual(prepared, "First movement.\nMove with control.")
        self.assertIn("loudnorm=I=-16", narration_audio_filter(32.0))

    def test_description_discloses_real_licensed_footage_ai_voice_and_safety(self):
        clip = StockClip(
            Path("sample.mp4"), "Pexels", "https://www.pexels.com/video/123", "Creator"
        )
        description = build_description(self.routine, [clip])
        self.assertIn("human-reviewed, licensed Pexels footage", description)
        self.assertIn("Pexels", description)
        self.assertIn("English AI voiceover", description)
        self.assertIn("Stop if you feel pain", description)
        self.assertIn("#Pilates", description)
        self.assertTrue(build_title(self.routine).endswith("| 3-Move Pilates Routine"))
        self.assertNotRegex(description + build_title(self.routine), r"[가-힣ㄱ-ㅎㅏ-ㅣ]")

    def test_comment_uses_routine_question(self):
        comment = build_engagement_comment(self.routine)
        self.assertIn("YOUR TURN:", comment)
        self.assertIn("Which of the three movements", comment)
        self.assertNotRegex(comment, r"[가-힣ㄱ-ㅎㅏ-ㅣ]")

    def test_preview_description_matches_pilates_format(self):
        exercise = routine_exercises(self.routine)[0]
        value = build_preview_description({
            "content_format": "pilates-real-video-v1",
            "title": "Morning Core",
            "exercises": [{
                "name_en": exercise.name_en,
                "prescription_en": exercise.prescription_en,
                "source_provider": "Pexels",
                "source_creator": "Creator",
                "source_url": "https://www.pexels.com/video/123",
            }],
            "engagement_comment": "Which move felt best today?",
        })
        self.assertIn("human-reviewed, licensed Pexels footage", value)
        self.assertIn("https://www.pexels.com/video/123", value)
        self.assertIn(exercise.name_en.title(), value)
        self.assertIn("#Pilates", value)
        self.assertNotRegex(value, r"[가-힣ㄱ-ㅎㅏ-ㅣ]")

    def test_every_scheduled_public_surface_is_english_only(self):
        by_id = {routine.routine_id: routine for routine in ROUTINES}
        with tempfile.TemporaryDirectory() as directory:
            for routine_id in REAL_VIDEO_ROUTINE_IDS:
                routine = by_id[routine_id]
                captions = Path(directory) / f"{routine_id}.ass"
                write_overlay_ass(captions, routine, 36.0)
                public_copy = "\n".join(
                    (
                        build_title(routine),
                        build_description(routine),
                        build_engagement_comment(routine),
                        build_narration(routine),
                        captions.read_text(encoding="utf-8-sig"),
                        " ".join(PUBLIC_TAGS),
                    )
                )
                self.assertNotRegex(public_copy, r"[가-힣ㄱ-ㅎㅏ-ㅣ]", routine_id)

    def test_preview_artifact_root_accepts_preserved_work_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            artifact_root = Path(directory) / "preview-promotion"
            nested_root = artifact_root / "work"
            (nested_root / "render").mkdir(parents=True)
            (nested_root / "metadata.json").write_text("{}", encoding="utf-8")
            (nested_root / "render" / "final_short.mp4").write_bytes(b"video")
            self.assertEqual(resolve_preview_dir(artifact_root), nested_root)

    def test_main_requires_licensed_real_video_provider(self):
        source = (ROOT / "src" / "main.py").read_text(encoding="utf-8")
        self.assertIn("StockMediaProvider", source)
        self.assertIn("build_clip_queries", source)
        self.assertIn('"pilates-fixed-model-real-video-v2"', source)
        self.assertIn("fetch_pexels_source", source)
        self.assertNotIn("research_exact_topic", source)
        self.assertNotIn("GeminiWriter", source)

    def test_renderer_uses_continuous_video_closeups_and_natural_grade(self):
        source = (ROOT / "src" / "pilates_renderer.py").read_text(encoding="utf-8")
        self.assertIn("_render_real_video_segment(exercise, clip", source)
        self.assertIn("scale=1458:2592", source)
        self.assertIn("xfade=transition=fade", source)
        self.assertIn("colorlevels=romax=0.97", _natural_grade_filter())
        self.assertIn("source-preserving natural grade", source)

    def test_renderer_reencodes_all_three_motion_segments(self):
        source = (ROOT / "src" / "pilates_renderer.py").read_text(encoding="utf-8")
        self.assertIn("[v0][v1][v2]concat=n=3:v=1:a=0[outv]", source)
        self.assertIn("_render_real_video_segment", source)
        self.assertNotIn('str(concat_file)', source)

    def test_media_quality_gate_requires_hd_continuous_video(self):
        self.assertEqual(MIN_VIDEO_EDGE, 720)
        self.assertGreaterEqual(MIN_FRAME_RATE, 20)
        source = (ROOT / "src" / "media_provider.py").read_text(encoding="utf-8")
        self.assertIn("avg_frame_rate", source)
        self.assertIn("nb_frames", source)
        self.assertIn("실제 움직임을 담은 연속 프레임", source)

    def test_visual_quality_gate_requires_exact_exercise_and_realistic_frames(self):
        self.assertEqual(GEMINI_VISION_MODEL, "gemini-3.7-flash")
        approved = {
            "approved": True,
            "exercise_match": 0.92,
            "realism": 0.94,
            "visibility": 0.88,
            "professional_attire": 0.9,
            "safe_framing": True,
        }
        self.assertTrue(meets_visual_thresholds(approved))
        self.assertTrue(meets_visual_thresholds({**approved, "exercise_match": 0.78, "realism": 0.80}))
        self.assertTrue(meets_visual_thresholds({**approved, "realism": 0.75, "visibility": 0.75}))
        self.assertFalse(meets_visual_thresholds({**approved, "exercise_match": 0.5}))
        self.assertFalse(meets_visual_thresholds({**approved, "safe_framing": False}))

    def test_gemini_visual_review_uses_three_frames_and_structured_json(self):
        result_payload = {
            "approved": True,
            "exercise_match": 0.95,
            "realism": 0.93,
            "visibility": 0.9,
            "professional_attire": 0.88,
            "safe_framing": True,
            "reason": "Correct dead bug with clear alignment.",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            frames = []
            for index in range(3):
                frame = root / f"frame-{index}.jpg"
                frame.write_bytes(b"test-jpeg-data")
                frames.append(frame)
            clip = StockClip(root / "clip.mp4", "Pexels", "https://example.com", duration=10)
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = {
                "candidates": [{"content": {"parts": [{"text": json.dumps(result_payload)}]}}]
            }
            with patch("visual_quality.extract_review_frames", return_value=frames), patch(
                "visual_quality.requests.post", return_value=response, create=True
            ) as request:
                review = GeminiVisualQualityGate("key").review(
                    clip, EXERCISES["dead-bug"], root / "review"
                )
        self.assertTrue(review["passed"])
        _, kwargs = request.call_args
        self.assertNotIn("key", request.call_args.args[0])
        self.assertEqual(kwargs["headers"]["x-goog-api-key"], "key")
        self.assertEqual(len(kwargs["json"]["contents"][0]["parts"]), 4)
        config = kwargs["json"]["generationConfig"]
        self.assertEqual(config["responseMimeType"], "application/json")
        self.assertIn("responseSchema", config)

    def test_gemini_visual_review_falls_back_when_a_model_is_retired(self):
        missing = Mock(status_code=404)
        available = Mock(status_code=200)
        available.raise_for_status.return_value = None
        available.json.return_value = {"candidates": []}
        with patch(
            "visual_quality.requests.post", side_effect=[missing, available], create=True
        ) as request, patch("visual_quality.time.sleep"):
            payload, model = GeminiVisualQualityGate("key")._generate([{"text": "review"}])
        self.assertEqual(payload, {"candidates": []})
        self.assertEqual(model, "gemini-3.5-flash")
        self.assertEqual(request.call_count, 2)

    def test_gemini_visual_review_retries_temporary_service_failure(self):
        unavailable = Mock(status_code=503)
        available = Mock(status_code=200)
        available.raise_for_status.return_value = None
        available.json.return_value = {"candidates": []}
        with patch(
            "visual_quality.requests.post", side_effect=[unavailable, available], create=True
        ) as request, patch("visual_quality.time.sleep") as delay:
            payload, model = GeminiVisualQualityGate("key")._generate([{"text": "review"}])
        self.assertEqual(payload, {"candidates": []})
        self.assertEqual(model, "gemini-3.7-flash")
        self.assertEqual(request.call_count, 2)
        delay.assert_any_call(1)

    def test_gemini_visual_review_uses_second_free_key_after_quota(self):
        limited = Mock(status_code=429)
        available = Mock(status_code=200)
        available.raise_for_status.return_value = None
        available.json.return_value = {"candidates": []}
        with patch.dict(
            "os.environ", {"GEMINI_API_KEY": "first", "GOOGLE_API_KEY": "second"}, clear=True
        ), patch(
            "visual_quality.requests.post", side_effect=[limited, available], create=True
        ) as request:
            gate = GeminiVisualQualityGate()
            payload, _ = gate._generate([{"text": "review"}])
        self.assertEqual(payload, {"candidates": []})
        self.assertEqual(request.call_count, 2)
        self.assertEqual(request.call_args.kwargs["headers"]["x-goog-api-key"], "second")

    def test_free_stock_plank_is_the_common_forearm_variant(self):
        plank = EXERCISES["modified-plank"]
        self.assertEqual(plank.name_en, "FOREARM PLANK")
        self.assertIn("발뒤꿈치", plank.cue_ko)
        self.assertNotIn("on knees", EXERCISE_VIDEO_SEARCH["modified-plank"])

    def test_manually_reviewed_real_sources_cover_the_priority_routine(self):
        priority = real_video_routine_candidates([], limit=1)[0]
        self.assertIn(priority.routine_id, REAL_VIDEO_ROUTINE_IDS)
        self.assertTrue(all(slug in PREFERRED_SOURCE_IDS for slug in priority.exercise_slugs))
        self.assertTrue(all(slug in FIXED_MODEL_SOURCES for slug in priority.exercise_slugs))

    def test_scheduled_fixed_model_routines_use_disjoint_reviewed_sources(self):
        by_id = {routine.routine_id: routine for routine in ROUTINES}
        seen = set()
        for routine_id in REAL_VIDEO_ROUTINE_IDS:
            routine = by_id[routine_id]
            source_ids = {FIXED_MODEL_SOURCES[slug] for slug in routine.exercise_slugs}
            self.assertEqual(len(source_ids), 3)
            self.assertFalse(seen.intersection(source_ids), routine_id)
            seen.update(source_ids)
        self.assertEqual(len(seen), len(REAL_VIDEO_ROUTINE_IDS) * 3)

    def test_published_fixed_model_sources_are_never_reused(self):
        first = real_video_routine_candidates([], today=date(2026, 8, 26), limit=1)[0]
        published = [{
            "content_format": FIXED_CONTENT_FORMAT,
            "routine_id": first.routine_id,
            "source_ids": [FIXED_MODEL_SOURCES[slug] for slug in first.exercise_slugs],
        }]
        remaining = real_video_routine_candidates(published, today=date(2026, 8, 27), limit=20)
        self.assertNotIn(first.routine_id, {item.routine_id for item in remaining})
        used = set(published[0]["source_ids"])
        self.assertTrue(all(
            not used.intersection(FIXED_MODEL_SOURCES[slug] for slug in routine.exercise_slugs)
            for routine in remaining
        ))

    def test_no_fallback_when_every_new_fixed_model_source_is_used(self):
        by_id = {routine.routine_id: routine for routine in ROUTINES}
        records = [{
            "content_format": FIXED_CONTENT_FORMAT,
            "routine_id": routine_id,
            "source_ids": [FIXED_MODEL_SOURCES[slug] for slug in by_id[routine_id].exercise_slugs],
        } for routine_id in REAL_VIDEO_ROUTINE_IDS]
        self.assertEqual(real_video_routine_candidates(records, limit=3), [])

    def test_exact_pexels_endpoint_prevents_search_from_swapping_the_model(self):
        with patch("media_provider.requests.Session", create=True):
            provider = StockMediaProvider(pexels_key="key")
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {
            "id": 7589748,
            "url": "https://www.pexels.com/video/7589748/",
            "duration": 10,
            "user": {"name": FIXED_MODEL_CREATOR},
            "video_files": [{
                "link": "https://videos.pexels.com/fixed.mp4",
                "file_type": "video/mp4",
                "width": 720,
                "height": 1280,
            }],
        }
        provider.session.get.return_value = response
        candidate = provider._get_pexels_by_id("7589748", "fixed model plank")
        self.assertEqual(candidate["source_id"], "7589748")
        self.assertEqual(candidate["creator"], FIXED_MODEL_CREATOR)
        self.assertIn("/v1/videos/videos/7589748", provider.session.get.call_args.args[0])

    def test_media_provider_rejects_mismatch_and_tries_next_candidate(self):
        with patch("media_provider.requests.Session", create=True):
            provider = StockMediaProvider(pexels_key="key")
        candidates = [
            {"provider": "Pexels", "source_id": "bad", "download_url": "bad", "height": 1920, "width": 1080, "duration": 10},
            {"provider": "Pexels", "source_id": "good", "download_url": "good", "height": 1920, "width": 1080, "duration": 10},
        ]
        reviews = iter([
            {"passed": False, "reason": "different exercise"},
            {"passed": True, "reason": "exact exercise"},
        ])
        with tempfile.TemporaryDirectory() as directory:
            def download(candidate, path):
                path.write_bytes(b"video")
                return StockClip(path, "Pexels", "https://example.com", source_id=candidate["source_id"])

            with patch.object(provider, "_search_pexels", return_value=candidates), patch.object(
                provider, "_search_pixabay", return_value=[]
            ), patch.object(provider, "_download", side_effect=download):
                clips = provider.fetch_clips(
                    ["dead bug"],
                    Path(directory),
                    limit=1,
                    min_required=1,
                    one_per_query=True,
                    visual_validator=lambda clip: next(reviews),
                )
        self.assertEqual(clips[0].source_id, "good")
        self.assertTrue(clips[0].visual_quality["passed"])

    def test_configuration_requires_one_free_video_provider(self):
        with patch.dict("os.environ", {}, clear=True):
            self.assertIn("PEXELS_API_KEY", check_configuration(False))
        with patch.dict(
            "os.environ", {"PEXELS_API_KEY": "key", "GEMINI_API_KEY": "key"}, clear=True
        ):
            self.assertEqual(check_configuration(False), [])
        with patch.dict(
            "os.environ", {"PIXABAY_API_KEY": "key", "GEMINI_API_KEY": "key"}, clear=True
        ):
            self.assertIn("PEXELS_API_KEY", check_configuration(False))

    def test_trend_profile_uses_public_short_performance_without_copying(self):
        search_payload = {"items": [{"id": {"videoId": "abc"}}]}
        details_payload = {"items": [{
            "id": "abc",
            "snippet": {
                "title": "Save this Pilates routine",
                "channelTitle": "Trainer",
                "publishedAt": "2026-08-01T00:00:00Z",
            },
            "statistics": {"viewCount": "100000", "likeCount": "5000", "commentCount": "100"},
            "contentDetails": {"duration": "PT30S"},
        }]}
        responses = []
        for payload in (search_payload, details_payload):
            response = Mock()
            response.raise_for_status.return_value = None
            response.json.return_value = payload
            responses.append(response)
        with patch("trend_scout.requests.get", side_effect=responses, create=True) as request:
            benchmarks = fetch_pilates_short_benchmarks(
                "key",
                now=datetime(2026, 8, 21, tzinfo=timezone.utc),
            )
        self.assertEqual(benchmarks[0]["video_id"], "abc")
        search_params = request.call_args_list[0].kwargs["params"]
        self.assertEqual(search_params["regionCode"], "US")
        self.assertEqual(search_params["relevanceLanguage"], "en")
        self.assertEqual(search_params["q"], "pilates workout shorts")
        profile = editing_profile(benchmarks)
        self.assertTrue(profile["save_cta"])
        self.assertFalse(profile["copied_titles"])
        self.assertFalse(profile["copied_footage"])

    def test_upload_payload_declares_english_and_synthetic_media(self):
        uploader = YouTubeUploader.__new__(YouTubeUploader)
        request = Mock()
        request.next_chunk.return_value = (None, {"id": "video-id"})
        videos = Mock()
        videos.insert.return_value = request
        uploader.youtube = Mock()
        uploader.youtube.videos.return_value = videos
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / "short.mp4"
            video.write_bytes(b"video")
            with patch("youtube_uploader.MediaFileUpload", return_value=Mock()):
                uploader.upload_video(
                    video,
                    title=build_title(self.routine),
                    description=build_description(self.routine),
                    tags=PUBLIC_TAGS,
                    privacy="public",
                )
        body = videos.insert.call_args.kwargs["body"]
        self.assertEqual(body["snippet"]["defaultLanguage"], "en")
        self.assertEqual(body["snippet"]["defaultAudioLanguage"], "en")
        self.assertEqual(body["snippet"]["categoryId"], "26")
        self.assertNotRegex(" ".join(body["snippet"]["tags"]), r"[가-힣ㄱ-ㅎㅏ-ㅣ]")
        self.assertEqual(body["status"]["privacyStatus"], "public")
        self.assertFalse(body["status"]["selfDeclaredMadeForKids"])
        self.assertTrue(body["status"]["containsSyntheticMedia"])

    def test_workflow_keeps_daily_public_schedule_and_tracks_assets(self):
        source = (ROOT / ".github" / "workflows" / "daily-upload.yml").read_text(encoding="utf-8")
        self.assertIn("Daily Hana Pilates Short", source)
        self.assertIn("cron: '35 1 * * *'", source)
        self.assertIn("assets/instructor/**", source)
        self.assertIn("PEXELS_API_KEY", source)
        self.assertIn("PIXABAY_API_KEY", source)
        self.assertIn("contact-sheet.jpg", source)
        self.assertIn("YOUTUBE_PRIVACY: public", source)
        self.assertIn("CONTENT_LANGUAGE: en", source)
        self.assertIn("TARGET_REGION: US", source)
        self.assertIn("TTS_LOCALE: en-US", source)
        self.assertIn("fonts-lato", source)
        self.assertIn("fc-match 'Lato'", source)

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
