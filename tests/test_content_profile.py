import tempfile
import unittest
from pathlib import Path

from core.classifier import category_for
from core.content_profile import content_profile, origin_hint


class ContentProfileTests(unittest.TestCase):
    def test_chatgpt_openai_filename_markers_are_separated_conservatively(self):
        self.assertEqual("chatgpt-openai", origin_hint(Path("ChatGPT Image 14 Aug 2026.png")))
        self.assertEqual("chatgpt-openai", origin_hint(Path("DALL-E_render.webp")))
        self.assertEqual("chatgpt-openai", origin_hint(Path("sora-video.mp4")))
        self.assertEqual("unknown", origin_hint(Path("family-photo.png")))

    def test_explicit_openai_image_metadata_survives_rename(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "renamed-image.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"tEXtSoftware\x00OpenAI GPT-Image" + b"x" * 64)
            profile = content_profile(path)
            self.assertEqual("chatgpt-openai", profile["origin"])
            self.assertEqual("metadata", profile["origin_evidence"])
            self.assertTrue(profile["is_ai_origin"])
            self.assertFalse(profile["is_ai_filename"])

    def test_ordinary_image_metadata_does_not_create_ai_origin(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "camera.png"
            path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"tEXtSoftware\x00CameraVendor" + b"x" * 64)
            self.assertEqual("unknown", origin_hint(path))

    def test_modern_media_formats_are_classified(self):
        self.assertEqual("Изображения", category_for(Path("photo.heic")))
        self.assertEqual("Изображения", category_for(Path("render.avif")))
        self.assertEqual("Видео", category_for(Path("camera.m2ts")))
        self.assertEqual("Аудио", category_for(Path("voice.aiff")))
        self.assertEqual("Чертежи", category_for(Path("part.sldprt")))

    def test_partial_download_is_never_routed(self):
        profile = content_profile(Path("large-video.mp4.crdownload"))
        self.assertTrue(profile["is_partial_download"])


if __name__ == "__main__":
    unittest.main()
