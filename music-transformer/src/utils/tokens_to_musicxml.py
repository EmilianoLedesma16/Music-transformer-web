# src/utils/tokens_to_musicxml.py
"""
Convierte tokens encoder (posicional) + IDs decoder (event-based) a MusicXML
de dos pentagramas (melodía + acompañamiento) usando music21.
"""
import music21
from music21 import stream, note, meter, tempo, key, dynamics, harmony, instrument, clef
from collections import defaultdict

from data.midi_tokenizer import (
    ID2TOKEN, PPQ as TOKENIZER_PPQ,
    SECONDS_PER_TICK, TARGET_TEMPO,
    MIN_PITCH, MAX_PITCH,
)

PPQ_ENC       = 8
TICKS_PER_BAR = 32

PPQ_DEC = TOKENIZER_PPQ

VELOCITY_DYNAMICS = {
    16:"ppp", 32:"pp", 48:"p",  64:"mp",
    80:"mf",  96:"f", 112:"ff", 127:"fff",
}

DUR_TOKEN_TICKS = {
    "<DUR_1>":1,  "<DUR_2>":2,  "<DUR_3>":3,  "<DUR_4>":4,
    "<DUR_6>":6,  "<DUR_8>":8,  "<DUR_12>":12, "<DUR_16>":16,
    "<DUR_T2>":2, "<DUR_T4>":4,
}

TEMPO_TOKEN_BPM = {
    "<TEMPO_60>":60,   "<TEMPO_80>":80,   "<TEMPO_100>":100,
    "<TEMPO_120>":120, "<TEMPO_140>":140, "<TEMPO_160>":160,
    "<TEMPO_180>":180, "<TEMPO_200>":200,
}


# ─────────────────────────────────────────────────────────────
# Parser ENCODER (representación posicional)
# ─────────────────────────────────────────────────────────────

def ticks_to_quarterLength_enc(ticks: int) -> float:
    return ticks / PPQ_ENC


def parse_tokens(tokens: list) -> tuple:
    meta = {"tempo": 120, "key": "C", "mode": "major",
            "timesig": "4/4", "genre": None, "mood": None}

    events     = []
    bar_chords = {}

    current_bar   = 1
    current_pos   = 0
    current_pitch = None
    current_dur   = None
    current_vel   = 80

    def flush():
        nonlocal current_pitch, current_dur
        if current_pitch is None or current_dur is None:
            return
        events.append({
            "bar":       current_bar,
            "pos_ticks": current_pos,
            "pitch":     current_pitch,
            "dur_ticks": current_dur,
            "velocity":  current_vel,
        })
        current_pitch = None
        current_dur   = None

    for tok in tokens:
        if tok.startswith("<TEMPO_"):
            meta["tempo"] = TEMPO_TOKEN_BPM.get(tok, 120)
        elif tok.startswith("<TIMESIG_"):
            p = tok[9:-1].split("_")
            meta["timesig"] = f"{p[0]}/{p[1]}"
        elif tok.startswith("<KEY_"):
            p = tok[5:-1].split("_")
            meta["key"]  = p[0].replace("s", "#")
            meta["mode"] = "major" if p[1] == "MAJ" else "minor"
        elif tok.startswith("<GENRE_"):
            meta["genre"] = tok[7:-1].capitalize()
        elif tok.startswith("<MOOD_"):
            meta["mood"] = tok[6:-1].capitalize()
        elif tok.startswith("<BAR_"):
            flush()
            current_bar = int(tok[5:-1])
            current_pos = 0
        elif tok.startswith("<POS_"):
            flush()
            current_pos = int(tok[5:-1])
        elif tok.startswith("<INST_"):
            if not meta.get("inst"):
                meta["inst"] = tok[6:-1].upper()
        elif tok.startswith("<CHORD_"):
            inner = tok[7:-1].split("_")
            root  = inner[0].replace("s", "#")
            qual  = inner[1] if len(inner) > 1 else "MAJ"
            bar_chords[current_bar] = (root, qual)
        elif tok.startswith("<PITCH_"):
            flush()
            current_pitch = int(tok[7:-1])
            current_dur   = None
            current_vel   = 80
        elif tok == "<REST>":
            flush()
            current_pitch = None
        elif tok in DUR_TOKEN_TICKS:
            current_dur = DUR_TOKEN_TICKS[tok]
        elif tok.startswith("<VEL_"):
            try:
                current_vel = int(tok[5:-1])
            except ValueError:
                pass
            flush()
        elif tok in ("<SOS>", "<EOS>", "<PAD>", "<UNK>"):
            pass

    flush()
    return events, meta, bar_chords


# ─────────────────────────────────────────────────────────────
# Parser DECODER (representación event-based)
# ─────────────────────────────────────────────────────────────

def parse_event_tokens(token_ids: list) -> tuple:
    meta = {"tempo": 120, "key": "C", "mode": "major",
            "timesig": "4/4", "genre": None, "mood": None}

    events     = []
    bar_chords = {}

    current_tick = 0
    active_vel   = 64
    open_notes   = {}

    skip_prefixes = (
        "<GENRE_", "<MOOD_", "<ENERGY_", "<INST_",
        "<TIMESIG_", "<KEY_", "<TEMPO_", "<CHORD_", "<BEAT_",
        "<BAR_", "<POS_",
        "<PITCH_", "<DUR_", "<VEL_", "<REST>",
    )

    for tid in token_ids:
        tok = ID2TOKEN.get(tid, "<UNK>")

        if tok in ("<SOS>", "<PAD>", "<UNK>", "<SEP>", "<MASK>"):
            continue
        if tok == "<EOS>":
            break

        if tok.startswith("<GENRE_"):
            meta["genre"] = tok[7:-1].capitalize()
            continue
        if tok.startswith("<MOOD_"):
            meta["mood"] = tok[6:-1].capitalize()
            continue
        if tok.startswith("<INST_"):
            meta["inst"] = tok[6:-1].capitalize()
            continue

        if any(tok.startswith(p) for p in skip_prefixes):
            continue

        if tok.startswith("<VELOCITY_"):
            try:
                active_vel = int(tok[len("<VELOCITY_"):-1])
            except ValueError:
                pass

        elif tok.startswith("<TIME_SHIFT_"):
            try:
                shift = int(tok[len("<TIME_SHIFT_"):-1])
                current_tick += max(0, shift)
            except ValueError:
                pass

        elif tok.startswith("<NOTE_ON_"):
            try:
                pitch = int(tok[len("<NOTE_ON_"):-1])
                if MIN_PITCH <= pitch <= MAX_PITCH:
                    open_notes[pitch] = (current_tick, active_vel)
            except ValueError:
                pass

        elif tok.startswith("<NOTE_OFF_"):
            try:
                pitch = int(tok[len("<NOTE_OFF_"):-1])
                if pitch in open_notes:
                    tick_on, vel = open_notes.pop(pitch)
                    dur_ticks = max(current_tick - tick_on, 1)
                    events.append({
                        "abs_tick":  tick_on,
                        "dur_ticks": dur_ticks,
                        "pitch":     pitch,
                        "velocity":  min(127, max(1, vel)),
                    })
            except ValueError:
                pass

    for pitch, (tick_on, vel) in open_notes.items():
        dur_ticks = max(current_tick - tick_on, 1)
        events.append({
            "abs_tick":  tick_on,
            "dur_ticks": dur_ticks,
            "pitch":     pitch,
            "velocity":  min(127, max(1, vel)),
        })

    ticks_per_bar_dec = PPQ_DEC * 4

    structured_events = []
    for ev in events:
        bar_idx  = ev["abs_tick"] // ticks_per_bar_dec
        pos_tick = ev["abs_tick"] %  ticks_per_bar_dec
        structured_events.append({
            "bar":       bar_idx + 1,
            "pos_ticks": pos_tick,
            "pitch":     ev["pitch"],
            "dur_ticks": ev["dur_ticks"],
            "velocity":  ev["velocity"],
        })

    return structured_events, meta, bar_chords


# ─────────────────────────────────────────────────────────────
# Construcción de pentagramas music21
# ─────────────────────────────────────────────────────────────

def _chord_symbol_str(root: str, qual: str) -> str:
    return (root + qual
        .replace("MAJ7", "maj7").replace("MIN7", "m7")
        .replace("DOM7", "7").replace("DIM7", "dim7")
        .replace("MAJ", "").replace("MIN", "m")
        .replace("DIM", "dim").replace("AUG", "aug"))


def _snap_ql(ql: float, minimum: float = 0.0) -> float:
    grid    = 0.0625
    snapped = round(round(ql / grid) * grid, 6)
    return max(snapped, minimum)


def events_to_part(events: list, meta: dict, bar_chords: dict,
                   part_name: str, inst_obj,
                   ppq: int = PPQ_ENC) -> stream.Part:

    def to_ql(ticks: int) -> float:
        return ticks / ppq

    p = stream.Part()
    p.id       = part_name
    p.partName = part_name

    ts_num     = int(meta["timesig"].split("/")[0])
    bar_dur_qn = float(ts_num)

    inst_class    = type(inst_obj).__name__ if inst_obj else ""
    bass_classes  = ("ElectricBass", "Bass", "BassGuitar", "Contrabass", "Tuba")
    use_bass_clef = inst_class in bass_classes

    if inst_obj:
        p.insert(0, inst_obj)
    p.insert(0, meter.TimeSignature(meta["timesig"]))
    p.insert(0, key.Key(meta["key"], meta["mode"]))
    p.insert(0, clef.BassClef() if use_bass_clef else clef.TrebleClef())

    if not events:
        p.makeMeasures(inPlace=True)
        return p

    prev_dynamic = None

    for ev in events:
        abs_ql = _snap_ql((ev["bar"] - 1) * bar_dur_qn + to_ql(ev["pos_ticks"]), minimum=0.0)
        dur_ql = _snap_ql(max(to_ql(ev["dur_ticks"]), 0.0625), minimum=0.0625)

        try:
            d = music21.duration.Duration(quarterLength=dur_ql)
        except Exception:
            d = music21.duration.Duration(quarterLength=0.25)

        n = note.Note(ev["pitch"])
        n.duration = d
        # n.volume.velocity genera dynamics="XX.XX" como atributo de <note>,
        # lo que corrompe el XML en la mayoría de editores. Se usan Dynamic() en su lugar.

        vel_bin = min(VELOCITY_DYNAMICS.keys(), key=lambda x: abs(x - ev["velocity"]))
        dyn_str = VELOCITY_DYNAMICS[vel_bin]
        if dyn_str != prev_dynamic:
            p.insert(abs_ql, dynamics.Dynamic(dyn_str))
            prev_dynamic = dyn_str

        p.insert(abs_ql, n)

    for bar_idx, (root, qual) in bar_chords.items():
        bar_ql = (bar_idx - 1) * bar_dur_qn
        try:
            p.insert(bar_ql, harmony.ChordSymbol(_chord_symbol_str(root, qual)))
        except Exception:
            pass

    p.makeMeasures(inPlace=True)
    # makeNotation se omite: introduce errores adicionales con duraciones no estándar.

    return p


# ─────────────────────────────────────────────────────────────
# API pública
# ─────────────────────────────────────────────────────────────

def tokens_to_musicxml(
    enc_tokens: list,
    dec_token_ids: list,
    output_path: str,
    tempo_bpm: float = 120.0,
    melody_name: str = "Melodía",
    accomp_name: str = "Acompañamiento",
) -> "music21.stream.Score":
    """
    Convierte tokens del encoder y IDs del decoder en un MusicXML de dos pentagramas.

    Args:
        enc_tokens:    Lista de strings — tokens del encoder (posicional).
        dec_token_ids: Lista de ints — salida directa de generate().
        output_path:   Ruta de salida (.xml).
        tempo_bpm:     Tempo original del MIDI de entrada.
    """
    enc_events, enc_meta, enc_chords = parse_tokens(enc_tokens)

    dec_tokens_str = [ID2TOKEN.get(tid, "<UNK>") for tid in dec_token_ids]
    n_note_on    = sum(1 for t in dec_tokens_str if t.startswith("<NOTE_ON_"))
    n_time_shift = sum(1 for t in dec_tokens_str if t.startswith("<TIME_SHIFT_"))
    n_pitch      = sum(1 for t in dec_tokens_str if t.startswith("<PITCH_"))
    n_bar        = sum(1 for t in dec_tokens_str if t.startswith("<BAR_"))

    event_based = (n_note_on + n_time_shift) > (n_pitch + n_bar)

    if event_based:
        dec_events, dec_meta, dec_chords = parse_event_tokens(dec_token_ids)
    else:
        dec_events, dec_meta, dec_chords = parse_tokens(dec_tokens_str)

    shared_meta = enc_meta.copy()
    shared_meta["tempo"] = max(40, min(int(tempo_bpm), 220))
    if not shared_meta.get("genre") and dec_meta.get("genre"):
        shared_meta["genre"] = dec_meta["genre"]
    if not shared_meta.get("mood") and dec_meta.get("mood"):
        shared_meta["mood"] = dec_meta["mood"]

    score = music21.stream.Score()
    score.metadata = music21.metadata.Metadata()

    title = "Acompañamiento Generado"
    if shared_meta.get("genre"):
        title += f" — {shared_meta['genre']}"
    if shared_meta.get("mood"):
        title += f" ({shared_meta['mood']})"
    score.metadata.title = title

    _mel_inst_map = {
        "PIANO":  instrument.Piano(),
        "BASS":   instrument.ElectricBass(),
        "GUITAR": instrument.Guitar(),
    }
    mel_inst = _mel_inst_map.get(enc_meta.get("inst", "GUITAR"), instrument.Guitar())
    mel_inst.partName = melody_name
    mel_part = events_to_part(enc_events, shared_meta, enc_chords,
                               melody_name, mel_inst, ppq=PPQ_ENC)

    mel_measures = mel_part.getElementsByClass(stream.Measure)
    if mel_measures:
        mel_measures[0].insert(0, tempo.MetronomeMark(number=shared_meta["tempo"]))

    acc_inst = instrument.ElectricBass()
    for tid in dec_token_ids:
        tok = ID2TOKEN.get(tid, "")
        if tok == "<INST_PIANO>":
            acc_inst = instrument.Piano()
            break
        elif tok == "<INST_GUITAR>":
            acc_inst = instrument.Guitar()
            break
        elif tok == "<INST_BASS>":
            acc_inst = instrument.ElectricBass()
            break

    acc_inst.partName = accomp_name
    dec_ppq = PPQ_DEC if event_based else PPQ_ENC
    acc_part = events_to_part(dec_events, shared_meta, dec_chords,
                               accomp_name, acc_inst, ppq=dec_ppq)

    score.append(mel_part)
    score.append(acc_part)

    try:
        score.write("musicxml", fp=str(output_path))
    except Exception as e:
        import warnings
        warnings.warn(f"write() falló ({e}), intentando exportación sin beams…")
        from music21.musicxml.m21ToXml import ScoreExporter
        import xml.etree.ElementTree as ET
        try:
            exporter = ScoreExporter(score)
            exporter.makeBeams = False
            root_element = exporter.parse()
            xml_bytes    = ET.tostring(root_element, encoding="unicode",
                                       xml_declaration=False)
            xml_str = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_bytes
            with open(str(output_path), "w", encoding="utf-8") as f:
                f.write(xml_str)
        except Exception as e2:
            raise RuntimeError(f"No se pudo exportar a MusicXML: {e} / {e2}") from e2

    return score
