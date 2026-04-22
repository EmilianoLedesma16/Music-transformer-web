"""
Pipeline de generación musical (generation_worker).

Recibe el MIDI transcrito y:
  1. Parsea el MIDI con pretty_midi
  2. Tokeniza la melodía (encoder tokens)
  3. Ejecuta inferencia con MusicTransformer (event-based decoder)
  4. Convierte tokens → MIDI de acompañamiento
  5. Convierte tokens → MusicXML (partitura de dos pentagramas)
  6. Sube ambos archivos a Supabase Storage
  7. Actualiza la BD con URLs y status=COMPLETED
"""
import logging
import os
import uuid
from pathlib import Path

import pretty_midi
import torch

from db import update_creacion
from storage import upload_file

STUB_GENERATION = os.environ.get("STUB_GENERATION", "").lower() in ("1", "true", "yes")

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
                "Coloca best_model.pt en music-transformer/checkpoints/."
            )
        ckpt = torch.load(CHECKPOINT_PATH, map_location=device)
        model.load_state_dict(ckpt["model_state"])
        model.eval()
        _model_cache[key] = (model, config)
        logger.info("MusicTransformer cargado desde %s (epoch %d, val_loss=%.4f)",
                    CHECKPOINT_PATH, ckpt.get("epoch", 0), ckpt.get("val_loss", 0))
    return _model_cache[key]


# ── Pipeline principal ────────────────────────────────────────────────────────
_ENERGY_LEVEL = {"LOW": 0.2, "MED": 0.5, "HIGH": 0.8}


def run(creacion_id: int, midi_path: str, genre: str, mood: str,
        energy: str, instrument: str, temperature: float, top_p: float) -> None:

    update_creacion(creacion_id, status="GENERATING",
                    progress_detail="Iniciando pipeline de generación…")

    if STUB_GENERATION:
        update_creacion(creacion_id, status="COMPLETED",
                        notes_generated=0, duration_seconds=0.0,
                        progress_detail="Stub activo — generación completada sin modelo")
        logger.info("STUB_GENERATION activo — creacion %d completada sin modelo", creacion_id)
        return

    try:
        from model.inference import generate, tokens_to_midi
        from data.midi_tokenizer import (
            detect_key, select_tracks, notes_to_token_sequence,
            inst_to_token, TOKEN2ID, ID2TOKEN,
        )
        from utils.tokens_to_musicxml import tokens_to_musicxml

        # ── 1. Parsear MIDI de entrada ────────────────────────────────────
        update_creacion(creacion_id, progress_detail="Parseando MIDI de entrada…")
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
        logger.info("Creacion %d — tonalidad: %s  tempo: %.0f BPM", creacion_id, key_token, tempo_bpm)

        # ── 2. Tokenizar melodía (encoder) ────────────────────────────────
        update_creacion(creacion_id, progress_detail="Tokenizando melodía de entrada…")
        device        = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info("Creacion %d — dispositivo: %s", creacion_id, device)

        energy_level = _ENERGY_LEVEL.get(energy.upper(), 0.5)
        enc_tokens = notes_to_token_sequence(
            melody_inst, pm, tempo_bpm, key_token,
            genre, mood, energy_level,
            inst_to_token(melody_inst), is_encoder=True,
        )
        if enc_tokens is None:
            raise ValueError("Melodía demasiado corta para tokenizar")

        # ── 3. Cargar modelo y preparar tensores ──────────────────────────
        update_creacion(creacion_id, progress_detail="Cargando modelo MusicTransformer…")
        model, config = _get_model(device)

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
            TOKEN2ID.get(f"<GENRE_{genre}>",      TOKEN2ID["<UNK>"]),
            TOKEN2ID.get(f"<MOOD_{mood}>",         TOKEN2ID["<UNK>"]),
            TOKEN2ID.get(f"<ENERGY_{energy.upper()}>", TOKEN2ID["<UNK>"]),
            TOKEN2ID.get(f"<INST_{instrument}>",   TOKEN2ID["<UNK>"]),
        ]

        # ── 4. Inferencia Transformer ─────────────────────────────────────
        update_creacion(creacion_id,
                        progress_detail=f"Generando acompañamiento ({genre} / {mood} / {instrument})…")
        gen_ids = generate(
            model, enc_ids, enc_mask, prompt, config, device,
            max_new_tokens=1024,
            temperature=temperature,
            top_p=top_p,
            top_k=50,
            repetition_penalty=1.3,
        )

        note_on_count = sum(1 for tid in gen_ids
                            if ID2TOKEN.get(tid, "").startswith("<NOTE_ON_"))
        logger.info("Creacion %d — %d tokens generados, %d NOTE_ON",
                    creacion_id, len(gen_ids), note_on_count)

        # ── 5. Tokens → MIDI de acompañamiento ───────────────────────────
        update_creacion(creacion_id, progress_detail="Convirtiendo a MIDI y MusicXML…")
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
        else:
            logger.warning("Creacion %d — MIDI sin notas (NOTE_ON=%d)", creacion_id, note_on_count)

        # ── 6. Tokens → MusicXML ─────────────────────────────────────────
        tokens_to_musicxml(
            enc_tokens=enc_tokens,
            dec_token_ids=gen_ids,
            output_path=str(out_xml),
            tempo_bpm=tempo_bpm,
            accomp_name=f"{instrument.capitalize()} ({genre})",
        )

        notes_count = len(out_pm.instruments[0].notes) if has_notes else 0
        duration    = out_pm.get_end_time()            if has_notes else 0.0

        # ── 7. Subir a Supabase ───────────────────────────────────────────
        update_creacion(creacion_id, progress_detail="Subiendo archivos a Supabase…")
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

        # ── 8. Actualizar BD ──────────────────────────────────────────────
        update_creacion(
            creacion_id,
            status           = "COMPLETED",
            midi_output_url  = midi_url,
            xml_output_url   = xml_url,
            notes_generated  = notes_count,
            duration_seconds = duration,
            progress_detail  = f"Completado — {notes_count} notas, {duration:.1f}s",
        )
        logger.info("Creacion %d completada. Notas: %d, Duración: %.1fs",
                    creacion_id, notes_count, duration)

    except Exception as exc:
        logger.exception("Error en generation_worker para creacion %d", creacion_id)
        update_creacion(creacion_id, status="FAILED",
                        error_message=str(exc), progress_detail=None)
        raise
