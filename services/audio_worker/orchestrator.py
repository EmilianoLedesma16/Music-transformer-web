"""
Full audio → MusicXML pipeline for the audio_worker.

Steps:
  1. Basic Pitch    : audio file  → MIDI
  2. midi_tokenizer : MIDI        → encoder token sequence
  3. MusicTransformer: enc tokens → decoder token ids
  4. tokens_to_musicxml: enc + dec tokens → .xml partitura
  5. tokens_to_midi  : dec ids    → .mid acompañamiento

music-transformer/src is bind-mounted at /app/mt_src and added to
PYTHONPATH by the Dockerfile, so all src.* imports resolve at runtime.
"""
import sys
import uuid
from pathlib import Path

import torch
import pretty_midi
from basic_pitch.inference import predict

from model.config import ModelConfig
from model.transformer import MusicTransformer
from model.inference import generate, tokens_to_midi
from data.midi_tokenizer import (
    detect_key, select_tracks, notes_to_token_sequence,
    inst_to_token, TOKEN2ID, ID2TOKEN,
)
from utils.tokens_to_musicxml import tokens_to_musicxml

from db import update_generation

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_DIR        = Path("/app/data")
MIDI_IN_DIR     = DATA_DIR / "processed" / "input_midis"
MIDI_OUT_DIR    = DATA_DIR / "processed" / "output_midis"
XML_OUT_DIR     = DATA_DIR / "output"    / "musicxml"
CHECKPOINT_PATH = Path("/app/checkpoints/best_model.pt")

for _d in (MIDI_IN_DIR, MIDI_OUT_DIR, XML_OUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

INST_PROGRAMS = {"BASS": 33, "PIANO": 0, "GUITAR": 25}


# ── Model loader (cached per process) ────────────────────────────────────────
_model_cache: dict = {}


def _get_model(device):
    key = str(device)
    if key not in _model_cache:
        config = ModelConfig()
        model  = MusicTransformer(config).to(device)
        ckpt   = torch.load(CHECKPOINT_PATH, map_location=device)
        model.load_state_dict(ckpt["model_state"])
        model.eval()
        _model_cache[key] = (model, config)
    return _model_cache[key]


# ── Main orchestration ────────────────────────────────────────────────────────
def run(gen_id: int, audio_path: str, genre: str, mood: str,
        instrument: str, temperature: float, top_p: float) -> None:

    try:
        # ── 1. Basic Pitch: audio → MIDI ─────────────────────────────────
        update_generation(gen_id, status="TRANSCRIBING")

        _, midi_data, _ = predict(audio_path)
        midi_path = MIDI_IN_DIR / f"{Path(audio_path).stem}.mid"
        midi_data.write(str(midi_path))
        update_generation(gen_id, midi_path=str(midi_path))

        # ── 2. Parse MIDI and build encoder tokens ────────────────────────
        update_generation(gen_id, status="GENERATING")

        pm = pretty_midi.PrettyMIDI(str(midi_path))
        melody_inst, _ = select_tracks(pm)
        if melody_inst is None:
            melody_inst = next((i for i in pm.instruments if not i.is_drum), None)
        if melody_inst is None:
            raise ValueError("MIDI has no usable tracks")

        tempo_bpm = pm.estimate_tempo()
        if not (30 < tempo_bpm < 300):
            tempo_bpm = 120.0
        key_token = detect_key(pm)

        device        = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model, config = _get_model(device)

        enc_tokens = notes_to_token_sequence(
            melody_inst, pm, tempo_bpm, key_token,
            genre, mood, 0.5,
            inst_to_token(melody_inst), is_encoder=True,
        )
        if enc_tokens is None:
            raise ValueError("Melody too short to tokenize")

        enc_tokens = enc_tokens[: config.max_seq_len]
        enc_ids    = torch.tensor(
            [TOKEN2ID.get(t, TOKEN2ID["<UNK>"]) for t in enc_tokens],
            dtype=torch.long,
        )
        enc_mask = torch.ones(len(enc_ids), dtype=torch.bool)

        pad_len  = config.max_seq_len - len(enc_ids)
        enc_ids  = torch.cat([enc_ids,  torch.zeros(pad_len, dtype=torch.long)])
        enc_mask = torch.cat([enc_mask, torch.zeros(pad_len, dtype=torch.bool)])

        prompt = [
            TOKEN2ID["<SOS>"],
            TOKEN2ID[f"<GENRE_{genre}>"],
            TOKEN2ID[f"<MOOD_{mood}>"],
            TOKEN2ID["<ENERGY_MED>"],
            TOKEN2ID[f"<INST_{instrument}>"],
        ]

        # ── 3. Transformer inference ──────────────────────────────────────
        gen_ids    = generate(
            model, enc_ids, enc_mask, prompt, config, device,
            max_new_tokens=1024,
            temperature=temperature,
            top_p=top_p,
        )
        dec_tokens = [ID2TOKEN.get(i, "<UNK>") for i in gen_ids]

        # ── 4. Output MIDI ────────────────────────────────────────────────
        out_pm   = tokens_to_midi(
            gen_ids,
            tempo_bpm=tempo_bpm,
            instrument_program=INST_PROGRAMS.get(instrument, 33),
        )
        slug         = str(uuid.uuid4())[:8]
        out_midi     = MIDI_OUT_DIR / f"gen_{gen_id}_{slug}.mid"
        out_xml      = XML_OUT_DIR  / f"gen_{gen_id}_{slug}.xml"

        has_notes = bool(out_pm.instruments and out_pm.instruments[0].notes)
        if has_notes:
            out_pm.write(str(out_midi))

        # ── 5. MusicXML ───────────────────────────────────────────────────
        tokens_to_musicxml(
            enc_tokens=enc_tokens,
            dec_tokens=dec_tokens,
            output_path=str(out_xml),
        )

        notes_count = len(out_pm.instruments[0].notes) if has_notes else 0
        duration    = out_pm.get_end_time()            if has_notes else 0.0

        update_generation(
            gen_id,
            status           = "COMPLETED",
            output_midi_path = str(out_midi) if has_notes else None,
            output_xml_path  = str(out_xml),
            notes_generated  = notes_count,
            duration_seconds = duration,
        )

    except Exception as exc:
        update_generation(gen_id, status="FAILED", error_message=str(exc))
        raise
