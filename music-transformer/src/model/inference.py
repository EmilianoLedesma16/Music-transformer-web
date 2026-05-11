# src/model/inference.py
"""
Generación autoregresiva con top-k + top-p, control de silencios y
penalización de repetición. Usa representación event-based en el decoder.
"""
import torch
import pretty_midi

from model.config import ModelConfig
from model.transformer import MusicTransformer
from data.midi_tokenizer import (
    detect_key, select_tracks, notes_to_token_sequence,
    inst_to_token, decode_event_tokens_to_midi,
    TOKEN2ID, ID2TOKEN, PPQ, TICKS_PER_BAR,
    MIN_PITCH, MAX_PITCH, VELOCITY_BINS,
    NOTE_ON_TOKENS, NOTE_OFF_TOKENS, TIME_SHIFT_TOKENS, VELOCITY_TOKENS,
    TARGET_TEMPO,
)

# ─────────────────────────────────────────────────────────────
# Constantes de generación
# ─────────────────────────────────────────────────────────────
MAX_CONSEC_TIME_SHIFTS     = 3
TIME_SHIFT_EXCESS_PENALTY  = 15.0
NOTE_ON_SILENCE_BONUS      = 18.0
SILENCE_BONUS_THRESHOLD    = 4
MAX_POLYPHONY              = 3
MAX_NOTE_OPEN_TICKS        = 64
MIN_NEW_TOKENS             = 200
MAX_NOTES_PER_TICK         = 2
MIN_FORCED_TIME_SHIFT_TICKS = 1
MAX_CONSEC_VELOCITY        = 2

_NOTE_ON_IDS    = frozenset(TOKEN2ID[t] for t in NOTE_ON_TOKENS   if t in TOKEN2ID)
_NOTE_OFF_IDS   = frozenset(TOKEN2ID[t] for t in NOTE_OFF_TOKENS  if t in TOKEN2ID)
_TIME_SHIFT_IDS = frozenset(TOKEN2ID[t] for t in TIME_SHIFT_TOKENS if t in TOKEN2ID)
_VELOCITY_IDS   = frozenset(TOKEN2ID[t] for t in VELOCITY_TOKENS   if t in TOKEN2ID)

_LONG_TIME_SHIFT_IDS = frozenset(
    TOKEN2ID[f"<TIME_SHIFT_{i}>"]
    for i in range(MIN_FORCED_TIME_SHIFT_TICKS, len(TIME_SHIFT_TOKENS) + 1)
    if f"<TIME_SHIFT_{i}>" in TOKEN2ID
)

# Mapa de tonalidad → pitches de la escala (clases de nota 0-11)
_SCALE_DEGREES = {
    "MAJ": [0, 2, 4, 5, 7, 9, 11],
    "MIN": [0, 2, 3, 5, 7, 8, 10],
}
_NOTE_NAMES = ["C", "Cs", "D", "Ds", "E", "F", "Fs", "G", "Gs", "A", "As", "B"]

def _build_out_of_scale_ids(key_token: str) -> frozenset:
    try:
        inner = key_token.strip("<>").replace("KEY_", "")
        parts = inner.rsplit("_", 1)
        root_name, mode = parts[0], parts[1]
        root = _NOTE_NAMES.index(root_name)
        scale_pcs = {(root + d) % 12 for d in _SCALE_DEGREES.get(mode, _SCALE_DEGREES["MAJ"])}
        out_ids = set()
        for t in NOTE_ON_TOKENS:
            tid = TOKEN2ID.get(t)
            if tid is None:
                continue
            pitch = int(t[len("<NOTE_ON_"):-1])
            if (pitch % 12) not in scale_pcs:
                out_ids.add(tid)
        return frozenset(out_ids)
    except Exception:
        return frozenset()


# ─────────────────────────────────────────────────────────────
# Funciones de muestreo
# ─────────────────────────────────────────────────────────────

def top_k_top_p_sampling(logits: torch.Tensor, temperature: float = 1.0,
                          top_k: int = 0, top_p: float = 0.9) -> int:
    logits = logits.float() / max(temperature, 1e-8)

    if top_k > 0:
        threshold = torch.topk(logits, min(top_k, logits.size(-1))).values[-1]
        logits[logits < threshold] = -float("inf")

    probs = torch.softmax(logits, dim=-1)
    sorted_probs, sorted_idx = torch.sort(probs, descending=True)
    cumulative = torch.cumsum(sorted_probs, dim=-1)
    sorted_probs[cumulative - sorted_probs > top_p] = 0.0

    if sorted_probs.sum() == 0:
        sorted_probs[0] = 1.0

    sorted_probs /= sorted_probs.sum()
    chosen_sorted = torch.multinomial(sorted_probs, 1)
    return sorted_idx[chosen_sorted].item()


def apply_repetition_penalty(logits: torch.Tensor, generated_ids: list,
                              penalty: float = 1.3) -> torch.Tensor:
    window = generated_ids[-64:]
    seen_note_on  = set(window) & _NOTE_ON_IDS
    seen_note_off = set(window) & _NOTE_OFF_IDS
    for tid in seen_note_on | seen_note_off:
        if logits[tid] > 0:
            logits[tid] /= penalty
        else:
            logits[tid] *= penalty
    return logits


def apply_silence_control(logits: torch.Tensor, consec_time_shifts: int,
                           accumulated_silence_ticks: int) -> torch.Tensor:
    if consec_time_shifts >= MAX_CONSEC_TIME_SHIFTS:
        for tid in _TIME_SHIFT_IDS:
            logits[tid] -= TIME_SHIFT_EXCESS_PENALTY * 10

    if accumulated_silence_ticks >= SILENCE_BONUS_THRESHOLD:
        for tid in _NOTE_ON_IDS:
            logits[tid] += NOTE_ON_SILENCE_BONUS

    return logits


# ─────────────────────────────────────────────────────────────
# Loop de generación
# ─────────────────────────────────────────────────────────────

_OUT_OF_SCALE_PENALTY = 3.0

@torch.no_grad()
def generate(model: "MusicTransformer", enc_ids: torch.Tensor,
             enc_mask: torch.Tensor, prompt_ids: list,
             config: ModelConfig, device: torch.device,
             max_new_tokens: int = 1024, temperature: float = 0.9,
             top_p: float = 0.9, top_k: int = 50,
             repetition_penalty: float = 1.3,
             key_token: str = "") -> list:

    model.eval()
    enc_ids  = enc_ids.unsqueeze(0).to(device)
    enc_mask = enc_mask.unsqueeze(0).to(device)
    memory   = model.encode(enc_ids, enc_mask)

    _out_of_scale_ids = _build_out_of_scale_ids(key_token) if key_token else frozenset()

    gen_ids = list(prompt_ids)
    eos_id  = TOKEN2ID.get("<EOS>", 2)
    pad_id  = TOKEN2ID.get("<PAD>", 0)
    unk_id  = TOKEN2ID.get("<UNK>", 4)

    _note_off_for = {}
    for t in NOTE_OFF_TOKENS:
        tid = TOKEN2ID.get(t)
        if tid is not None:
            try:
                pitch = int(t[len("<NOTE_OFF_"):-1])
                _note_off_for[pitch] = tid
            except ValueError:
                pass

    _note_on_pitch = {}
    for t in NOTE_ON_TOKENS:
        tid = TOKEN2ID.get(t)
        if tid is not None:
            try:
                pitch = int(t[len("<NOTE_ON_"):-1])
                _note_on_pitch[tid] = pitch
            except ValueError:
                pass

    consec_time_shifts        = 0
    accumulated_silence_ticks = 0
    current_tick              = 0
    consec_velocity           = 0
    notes_since_time_shift    = 0

    open_notes: dict = {}
    n_new = 0

    for _ in range(max_new_tokens):
        for pitch, tick_opened in list(open_notes.items()):
            if current_tick - tick_opened > MAX_NOTE_OPEN_TICKS:
                off_id = _note_off_for.get(pitch)
                if off_id is not None:
                    gen_ids.append(off_id)
                del open_notes[pitch]

        tgt      = torch.tensor([gen_ids], dtype=torch.long, device=device)
        tgt_mask = torch.ones(1, len(gen_ids), dtype=torch.bool, device=device)

        if tgt.size(1) > config.max_seq_len:
            tgt      = tgt[:, -config.max_seq_len:]
            tgt_mask = tgt_mask[:, -config.max_seq_len:]

        with torch.amp.autocast(device_type=device.type,
                                dtype=torch.float16 if device.type == "cuda" else torch.bfloat16,
                                enabled=device.type in ("cuda", "cpu")):
            logits = model.decode(tgt, memory, tgt_mask, enc_mask)

        next_logits = logits[0, -1, :].clone()
        next_logits[pad_id] = -float("inf")
        next_logits[unk_id] = -float("inf")

        if notes_since_time_shift >= MAX_NOTES_PER_TICK and consec_velocity == 0:
            mask_ts = torch.full_like(next_logits, -float("inf"))
            for tid in _LONG_TIME_SHIFT_IDS:
                mask_ts[tid] = next_logits[tid]
            next_logits = mask_ts

        elif consec_velocity > 0:
            eos_allowed = n_new >= MIN_NEW_TOKENS
            keep = _NOTE_ON_IDS | ({eos_id} if eos_allowed else set())
            mask = torch.full_like(next_logits, -float("inf"))
            for tid in keep:
                mask[tid] = next_logits[tid]
            next_logits = mask
        else:
            if n_new < MIN_NEW_TOKENS:
                next_logits[eos_id] = -float("inf")
            if len(open_notes) >= MAX_POLYPHONY:
                for tid in _NOTE_ON_IDS:
                    next_logits[tid] = -float("inf")

        next_logits = apply_repetition_penalty(next_logits, gen_ids, penalty=repetition_penalty)
        next_logits = apply_silence_control(next_logits, consec_time_shifts, accumulated_silence_ticks)

        if _out_of_scale_ids:
            for tid in _out_of_scale_ids:
                if next_logits[tid] > -float("inf"):
                    next_logits[tid] -= _OUT_OF_SCALE_PENALTY

        next_id = top_k_top_p_sampling(
            next_logits, temperature=temperature, top_k=top_k, top_p=top_p
        )

        if next_id in _NOTE_ON_IDS:
            pitch = _note_on_pitch[next_id]
            if pitch in open_notes:
                off_id = _note_off_for.get(pitch)
                if off_id is not None:
                    gen_ids.append(off_id)
                del open_notes[pitch]

        gen_ids.append(next_id)
        n_new += 1

        if next_id in _TIME_SHIFT_IDS:
            consec_time_shifts    += 1
            consec_velocity        = 0
            notes_since_time_shift = 0
            tok = ID2TOKEN.get(next_id, "")
            try:
                shift_val = int(tok[len("<TIME_SHIFT_"):-1])
            except (ValueError, IndexError):
                shift_val = 1
            accumulated_silence_ticks += shift_val
            current_tick              += shift_val

        elif next_id in _VELOCITY_IDS:
            consec_velocity   += 1
            consec_time_shifts = 0

        elif next_id in _NOTE_ON_IDS:
            pitch = _note_on_pitch[next_id]
            open_notes[pitch]         = current_tick
            consec_time_shifts        = 0
            consec_velocity           = 0
            accumulated_silence_ticks = 0
            notes_since_time_shift   += 1

        elif next_id in _NOTE_OFF_IDS:
            tok = ID2TOKEN.get(next_id, "")
            try:
                pitch = int(tok[len("<NOTE_OFF_"):-1])
                open_notes.pop(pitch, None)
            except (ValueError, IndexError):
                pass
            consec_time_shifts        = 0
            accumulated_silence_ticks = 0

        if next_id == eos_id:
            break

    for pitch in list(open_notes.keys()):
        off_id = _note_off_for.get(pitch)
        if off_id is not None:
            gen_ids.append(off_id)

    return gen_ids


# ─────────────────────────────────────────────────────────────
# tokens → MIDI (delega en el tokenizador para consistencia)
# ─────────────────────────────────────────────────────────────

def tokens_to_midi(token_ids: list, tempo_bpm: float = 120.0,
                   instrument_program: int = 33) -> pretty_midi.PrettyMIDI:
    pm = decode_event_tokens_to_midi(token_ids, instrument_program=instrument_program)

    if abs(tempo_bpm - TARGET_TEMPO) > 1.0 and pm.instruments:
        scale = TARGET_TEMPO / tempo_bpm
        for inst in pm.instruments:
            for note in inst.notes:
                note.start *= scale
                note.end   *= scale

    return pm
