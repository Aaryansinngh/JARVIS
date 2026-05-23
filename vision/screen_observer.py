from PIL import ImageGrab
import easyocr
import numpy as np
import time


class ScreenObserver:

    def __init__(self):

        self._reader = easyocr.Reader(
            ["en"],
            gpu=False,
        )

        self._last_text = ""
        self._last_capture_time = 0

    # =====================================================
    # CAPTURE SCREEN
    # =====================================================

    def capture_screen(self):

        screenshot = ImageGrab.grab()

        return np.array(screenshot)

    # =====================================================
    # OCR SCREEN
    # =====================================================

    def read_screen_text(self):

        image = self.capture_screen()

        results = self._reader.readtext(image)

        text_chunks = []

        for result in results:

            detected_text = result[1]

            text_chunks.append(detected_text)

        full_text = "\n".join(text_chunks)

        self._last_text = full_text

        self._last_capture_time = time.time()

        return full_text

    # =====================================================
    # QUICK TEXT SEARCH
    # =====================================================

    def screen_contains(
        self,
        phrase: str,
    ) -> bool:

        return phrase.lower() in (
            self._last_text.lower()
        )