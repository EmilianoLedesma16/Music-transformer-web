"""
CNN14 instrument classifier — PANNs pretrained on AudioSet.

En el primer arranque, panns_inference descarga automáticamente el
checkpoint CNN14 (~325 MB) desde Zenodo a ~/panns_data/.
El volumen Docker 'panns_data' persiste ese directorio entre reinicios.

Estrategia de clasificación:
  1. Carga el audio a 32 kHz mono (requerido por CNN14).
  2. Ejecuta inferencia → vector de 527 probabilidades (AudioSet).
  3. Busca dinámicamente los índices de Guitar / Bass guitar / Piano
     en la lista de etiquetas de panns_inference.
  4. El instrumento con mayor probabilidad máxima gana.
"""
import logging
import numpy as np
import librosa

logger = logging.getLogger(__name__)

VALID_INSTRUMENTS = {"piano", "guitar", "bass"}
MIN_CONFIDENCE = 0.05  # score mínimo para considerar un instrumento detectado

# Palabras clave para filtrar etiquetas AudioSet por instrumento
_KEYWORDS: dict[str, list[str]] = {
    "guitar": ["guitar"],          # incluye Acoustic guitar, Electric guitar…
    "bass":   ["bass guitar"],     # Bass guitar específicamente
    "piano":  ["piano"],           # Piano, Electric piano…
}
# Excluir etiquetas que contengan estas palabras del grupo guitar
_GUITAR_EXCLUDE = ["bass"]

_indices: dict[str, list[int]] | None = None
_tagger = None


def _build_indices() -> dict[str, list[int]]:
    """Construye los índices AudioSet para cada instrumento (una vez)."""
    from panns_inference import labels as panns_labels
    result: dict[str, list[int]] = {}
    for inst, keywords in _KEYWORDS.items():
        idx_list = []
        for i, label in enumerate(panns_labels):
            label_lower = label.lower()
            match = any(kw in label_lower for kw in keywords)
            if inst == "guitar":
                match = match and not any(ex in label_lower for ex in _GUITAR_EXCLUDE)
            if match:
                idx_list.append(i)
        result[inst] = idx_list
        logger.info("CNN14 índices %s → %s", inst, idx_list)
    return result


def _get_tagger():
    """Carga (y cachea) el modelo CNN14. Primera llamada descarga el checkpoint."""
    global _tagger, _indices
    if _tagger is None:
        logger.info("Cargando CNN14 (primera llamada puede tardar: descarga ~325 MB)...")
        from panns_inference import AudioTagging
        _tagger  = AudioTagging(checkpoint_path=None, device="cpu")
        _indices = _build_indices()
        logger.info("CNN14 listo.")
    return _tagger


def classify_instrument(audio_path: str) -> tuple[str, bool]:
    """
    Clasifica el instrumento principal del audio.

    Returns:
        (detected_instrument, is_valid)
        detected_instrument: "piano" | "guitar" | "bass" | "unknown"
        is_valid: True si el instrumento está en VALID_INSTRUMENTS
    """
    # Cargar audio a 32 kHz mono (requerido por CNN14)
    waveform, _ = librosa.load(audio_path, sr=32_000, mono=True)
    waveform = waveform[None, :].astype(np.float32)   # (1, T)

    tagger = _get_tagger()
    clipwise_output, _ = tagger.inference(waveform)   # (1, 527)
    probs = clipwise_output[0]                         # (527,)

    scores: dict[str, float] = {}
    for inst, idx_list in _indices.items():
        scores[inst] = float(np.max(probs[idx_list])) if idx_list else 0.0

    logger.info("CNN14 scores: %s", {k: f"{v:.3f}" for k, v in scores.items()})

    detected = max(scores, key=scores.get)
    if scores[detected] < MIN_CONFIDENCE:
        logger.info("CNN14: ningún instrumento supera umbral %.2f — rechazando audio", MIN_CONFIDENCE)
        return "unknown", False

    return detected, detected in VALID_INSTRUMENTS
