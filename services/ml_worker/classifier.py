"""
CNN14 instrument classifier.

TODO (Omar): Replace the mock block below with real CNN14 inference:

    import torch, torchaudio
    from pathlib import Path

    CHECKPOINT = Path("/app/checkpoints/cnn14_finetuned.pt")
    LABEL_MAP  = {0: "piano", 1: "guitar", 2: "bass", ...}

    def classify_instrument(audio_path):
        waveform, sr = torchaudio.load(audio_path)
        model = CNN14(...)
        model.load_state_dict(torch.load(CHECKPOINT, map_location="cpu"))
        model.eval()
        with torch.no_grad():
            logits = model(waveform)
        detected = LABEL_MAP[logits.argmax().item()]
        return detected, detected in VALID_INSTRUMENTS
"""

VALID_INSTRUMENTS = {"piano", "guitar", "bass"}


def classify_instrument(audio_path):
    """
    Returns (detected_instrument: str, is_valid: bool).
    """
    # ── MOCK: replace with real CNN14 inference ──────────────────────────
    detected = "guitar"
    # ────────────────────────────────────────────────────────────────────
    return detected, detected in VALID_INSTRUMENTS
