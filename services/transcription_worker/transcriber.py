"""
Transcripción audio → MIDI usando Basic Pitch.
Adaptado de music-transformer/src/input_process/transcriber.py
"""
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MIDI_DIR = Path("/app/data/processed/input_midis")
MIDI_DIR.mkdir(parents=True, exist_ok=True)


def audio_to_midi(audio_path: str, creacion_id: int) -> str:
    """
    Convierte un archivo de audio a MIDI con Basic Pitch.

    Args:
        audio_path:    ruta local al archivo de audio
        creacion_id:   id de la creacion (para nombrar el MIDI)

    Returns:
        Ruta local del archivo MIDI generado.
    """
    from basic_pitch.inference import predict

    logger.info("Transcribiendo %s → MIDI...", audio_path)
    _, midi_data, _ = predict(audio_path)

    midi_path = MIDI_DIR / f"creacion_{creacion_id}.mid"
    midi_data.write(str(midi_path))

    logger.info("MIDI guardado en %s", midi_path)
    return str(midi_path)
