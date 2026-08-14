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
