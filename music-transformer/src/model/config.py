# src/model/config.py
from dataclasses import dataclass


@dataclass
class ModelConfig:
    # IMPORTANTE: actualizar si el vocabulario cambia.
    # Con tokens event-based el vocabulario creció de ~355 a ~525.
    vocab_size:     int   = 525
    max_seq_len:    int   = 1536
    pad_id:         int   = 0

    # ── Arquitectura ───────────────────────────────────────────────────
    d_model:        int   = 512
    n_heads:        int   = 8
    n_enc_layers:   int   = 6
    n_dec_layers:   int   = 6
    d_ff:           int   = 2048
    dropout:        float = 0.15

    # ── Entrenamiento ──────────────────────────────────────────────────
    batch_size:     int   = 4
    grad_accum:     int   = 8
    learning_rate:  float = 5e-5
    warmup_steps:   int   = 500
    max_epochs:     int   = 30
    clip_grad:      float = 1.0

    # ── Pesos de pérdida por tipo de token ─────────────────────────────
    time_shift_weight: float = 0.3
    note_on_weight:    float = 2.0
    note_off_weight:   float = 1.5
    velocity_weight:   float = 2.0

    # ── Datos ──────────────────────────────────────────────────────────
    train_h5:   str = "data/tokens/train.h5"
    val_h5:     str = "data/tokens/val.h5"
    test_h5:    str = "data/tokens/test.h5"
    vocab_json: str = "data/tokens/vocabulary.json"
    ckpt_dir:   str = "checkpoints/v2"
