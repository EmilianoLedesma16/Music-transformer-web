"""
Pipeline de generación musical (generation_worker).

Recibe la ruta del MIDI transcrito por el transcription_worker y:
  1. Parsea el MIDI con pretty_midi
  2. Tokeniza la melodía (encoder tokens)
  3. Ejecuta inferencia con MusicTransformer
  4. Convierte tokens → MIDI de acompañamiento
  5. Convierte tokens → MusicXML (partitura)
  6. Sube ambos archivos a Supabase Storage
  7. Actualiza la BD con las URLs y status=COMPLETED

music-transformer/src está montado en /app/mt_src y añadido a PYTHONPATH.
"""
import logging
import uuid
from pathlib import Path

import torch
import pretty_midi

from db import update_creacion
from storage import upload_file

logger = logging.getLogger(__name__)

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_DIR        = Path("/app/data")
MIDI_OUT_DIR    = DATA_DIR / "processed" / "output_midis"
XML_OUT_DIR     = DATA_DIR / "output"    / "musicxml"
CHECKPOINT_PATH = Path("/app/checkpoints/best_model.pt")

for _d in (MIDI_OUT_DIR, XML_OUT_DIR):
    _d.mkdir(parents=True, exist_ok=True)

INST_PROGRAMS = {"BASS": 33, "PIANO": 0, "GUITAR": 25}

# ── Model cache (una instancia por proceso worker) ────────────────────────────
_model_cache: dict = {}


def _get_model(device):
    key = str(device)
    if key not in _model_cache:
        from model.config import ModelConfig
        from model.transformer import MusicTransformer
        config = ModelConfig()
        model  = MusicTransformer(config).to(device)
        if not CHECKPOINT_PATH.exists():
            raise FileNotFoundError(
                f"Checkpoint no encontrado en {CHECKPOINT_PATH}. "
                "Coloca best_model.pt en el volumen model_checkpoints."
            )
        ckpt = torch.load(CHECKPOINT_PATH, map_location=device)
        model.load_state_dict(ckpt["model_state"])
        model.eval()
        _model_cache[key] = (model, config)
        logger.info("MusicTransformer cargado desde %s", CHECKPOINT_PATH)
    return _model_cache[key]


# ── Pipeline principal ────────────────────────────────────────────────────────
def run(creacion_id: int, midi_path: str, genre: str, mood: str,
        instrument: str, temperature: float, top_p: float) -> None:

    update_creacion(creacion_id, status="GENERATING")

    try:
        from model.inference import generate, tokens_to_midi
        from data.midi_tokenizer import (
            detect_key, select_tracks, notes_to_token_sequence,
            inst_to_token, TOKEN2ID, ID2TOKEN,
        )
        from utils.tokens_to_musicxml import tokens_to_musicxml

        # ── 1. Parsear MIDI de entrada ────────────────────────────────────
        pm = pretty_midi.PrettyMIDI(midi_path)
        melody_inst, _ = select_tracks(pm)
        if melody_inst is None:
            melody_inst = next((i for i in pm.instruments if not i.is_drum), None)
        if melody_inst is None:
            raise ValueError("El MIDI no tiene pistas utilizables")

        tempo_bpm = pm.estimate_tempo()
        if not (30 < tempo_bpm < 300):
            tempo_bpm = 120.0
        key_token = detect_key(pm)

        # ── 2. Tokenizar melodía (encoder) ────────────────────────────────
        device        = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model, config = _get_model(device)

        enc_tokens = notes_to_token_sequence(
            melody_inst, pm, tempo_bpm, key_token,
            genre, mood, 0.5,
            inst_to_token(melody_inst), is_encoder=True,
        )
        if enc_tokens is None:
            raise ValueError("Melodía demasiado corta para tokenizar")

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

        # ── 3. Inferencia Transformer ─────────────────────────────────────
        gen_ids    = generate(
            model, enc_ids, enc_mask, prompt, config, device,
            max_new_tokens=1024,
            temperature=temperature,
            top_p=top_p,
        )
        dec_tokens = [ID2TOKEN.get(i, "<UNK>") for i in gen_ids]

        # ── 4. Tokens → MIDI de acompañamiento ───────────────────────────
        out_pm = tokens_to_midi(
            gen_ids,
            tempo_bpm=tempo_bpm,
            instrument_program=INST_PROGRAMS.get(instrument, 33),
        )
        slug     = str(uuid.uuid4())[:8]
        out_midi = MIDI_OUT_DIR / f"gen_{creacion_id}_{slug}.mid"
        out_xml  = XML_OUT_DIR  / f"gen_{creacion_id}_{slug}.xml"

        has_notes = bool(out_pm.instruments and out_pm.instruments[0].notes)
        if has_notes:
            out_pm.write(str(out_midi))

        # ── 5. Tokens → MusicXML ─────────────────────────────────────────
        tokens_to_musicxml(
            enc_tokens=enc_tokens,
            dec_tokens=dec_tokens,
            output_path=str(out_xml),
        )

        notes_count = len(out_pm.instruments[0].notes) if has_notes else 0
        duration    = out_pm.get_end_time()            if has_notes else 0.0

        # ── 6. Subir a Supabase ───────────────────────────────────────────
        midi_url = None
        xml_url  = None

        if has_notes:
            midi_url = upload_file(
                str(out_midi),
                f"outputs/{creacion_id}/accompaniment.mid",
                "audio/midi",
            )
        xml_url = upload_file(
            str(out_xml),
            f"outputs/{creacion_id}/partitura.xml",
            "application/xml",
        )

        # ── 7. Actualizar BD ──────────────────────────────────────────────
        update_creacion(
            creacion_id,
            status           = "COMPLETED",
            midi_output_url  = midi_url,
            xml_output_url   = xml_url,
            notes_generated  = notes_count,
            duration_seconds = duration,
        )
        logger.info("Creacion %d completada. Notas: %d, Duración: %.1fs",
                    creacion_id, notes_count, duration)

    except Exception as exc:
        logger.exception("Error en generation_worker para creacion %d", creacion_id)
        update_creacion(creacion_id, status="FAILED", error_message=str(exc))
        raise
