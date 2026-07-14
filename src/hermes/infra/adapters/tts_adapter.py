import os

import edge_tts

from hermes.core.interfaces import AudioPort


class EdgeTtsAdapter(AudioPort):
    def __init__(self, output_dir: str, voice: str = "pt-BR-AntonioNeural"):
        self.output_dir = output_dir
        self.voice = voice
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_audio(self, date_ref: str, text: str) -> str:
        if not text:
            return ""

        audio_filename = f"podcast_{date_ref}.mp3"
        audio_path = os.path.join(self.output_dir, audio_filename)

        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(audio_path)

        return audio_path
