"""Shared code for DFU training pipeline (config, data, models, trainer, tuner)."""

import os
import sys
import warnings
import json
import gc
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_curve, auc, roc_auc_score, classification_report
)

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models
from tensorflow.keras.optimizers import Adam, RMSprop, SGD
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from tensorflow.keras.applications import efficientnet, resnet50, convnext

import optuna
from optuna.samplers import TPESampler

warnings.filterwarnings('ignore')
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL', '2')
import logging
logging.getLogger('absl').setLevel(logging.ERROR)

SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

for gpu in tf.config.list_physical_devices('GPU'):
    tf.config.experimental.set_memory_growth(gpu, True)

CONFIG = {
    'data_source':         '/home/ntphoto/DFU/INAOE_Preprocessed',
    'checkpoint_dir':      './model_checkpoints',
    'results_dir':         './results',
    'img_size':            (224, 224),
    'batch_size_default':  32,
    'max_epochs':          50,
    'phase1_patience':     5,
    'phase2_patience':     15,
    'n_folds':             5,
    'test_split':          0.2,
    'optuna_trials':       10,
    'phase2_lr_decay':        0.95,
    'phase2_decay_steps':     100,
    'augmentation_rotation':  10,   # degrees — applied to training set only
}

os.makedirs(CONFIG['checkpoint_dir'], exist_ok=True)
os.makedirs(CONFIG['results_dir'], exist_ok=True)


def make_logger(tag: str):
    """Return a log_message function that writes to a tag-specific file."""
    log_file = os.path.join(
        CONFIG['results_dir'],
        f"{tag}_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    )

    def log_message(message: str, print_also: bool = True):
        with open(log_file, 'a') as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        if print_also:
            print(message, flush=True)

    log_message(f"=== Log file: {log_file} ===")
    return log_message


# ── Data loading ─────────────────────────────────────────
def load_preprocessed_inaoe(data_dir: str, log=print):
    images, labels = [], []
    for group_idx, group in enumerate(['CT', 'DM']):
        group_dir = os.path.join(data_dir, group)
        if not os.path.exists(group_dir):
            raise FileNotFoundError(f"Group directory not found: {group_dir}")
        for npy_file in sorted(f for f in os.listdir(group_dir) if f.endswith('.npy')):
            images.append(np.load(os.path.join(group_dir, npy_file)))
            labels.append(group_idx)
    images = np.array(images, dtype=np.float32)
    labels = np.array(labels, dtype=np.int32)
    log(f"Loaded INAOE: {len(images)} images, shape={images.shape}, "
        f"CT={int(np.sum(labels == 0))}, DM={int(np.sum(labels == 1))}")
    assert images.shape[1:] == (224, 224, 3)
    assert images.min() >= 0 and images.max() <= 1
    assert len(np.unique(labels)) == 2
    return images, labels


def create_fold_splits(images, labels, n_splits=5, test_split=0.2, random_state=SEED):
    skf = StratifiedKFold(
        n_splits=max(2, int(round(1.0 / test_split))),
        shuffle=True, random_state=random_state
    )
    test_indices = None
    for fold_idx, (train_val_idx, test_idx) in enumerate(skf.split(images, labels)):
        if fold_idx == 0:
            test_indices = test_idx
            break

    train_val_orig = train_val_idx
    skf_folds = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    fold_indices = []
    for fi, (train_idx, val_idx) in enumerate(skf_folds.split(images[train_val_orig], labels[train_val_orig])):
        fold_indices.append({
            'fold': fi,
            'train_idx': train_val_orig[train_idx],
            'val_idx':   train_val_orig[val_idx],
        })
    return fold_indices, test_indices


# ── Models ───────────────────────────────────────────────
class ExponentialDecayScheduler(tf.keras.optimizers.schedules.LearningRateSchedule):
    def __init__(self, initial_lr, decay_rate=0.95, decay_steps=100):
        self.initial_lr = initial_lr
        self.decay_rate = decay_rate
        self.decay_steps = decay_steps

    def __call__(self, step):
        return self.initial_lr * tf.pow(self.decay_rate, tf.cast(step, tf.float32) / self.decay_steps)

    def get_config(self):
        return {"initial_lr": self.initial_lr,
                "decay_rate": self.decay_rate,
                "decay_steps": self.decay_steps}



class DFUModelTrainer:
    def __init__(self, model_name, base_model, dropout_rate=0.5, l2_reg=1e-5,
                 dense_units=(256, 64), log=print):
        self.model_name = model_name
        self.base_model = base_model
        self.dropout_rate = dropout_rate
        self.l2_reg = l2_reg
        self.dense_units = dense_units
        self.log = log
        self.model = None
        self.phase1_history = None
        self.phase2_history = None

    @property
    def phase1_best_epoch(self):
        """Total epochs run in phase 1 (= stopping epoch, used as training budget)."""
        if self.phase1_history is None:
            return None
        h = self.phase1_history.history
        if 'val_loss' not in h:
            return None
        return len(h['val_loss'])

    @property
    def phase2_best_epoch(self):
        """Total epochs run in phase 2 (= stopping epoch, used as training budget)."""
        if self.phase2_history is None:
            return None
        h = self.phase2_history.history
        if 'val_loss' not in h:
            return None
        return len(h['val_loss'])

    def build_model(self):
        self.base_model.trainable = False
        inputs = layers.Input(shape=(224, 224, 3))
        x = self.base_model(inputs, training=False)
        x = layers.GlobalAveragePooling2D()(x)
        x = layers.Dense(self.dense_units[0], activation='relu',
                         kernel_regularizer=keras.regularizers.l2(self.l2_reg))(x)
        x = layers.Dropout(self.dropout_rate)(x)
        x = layers.Dense(self.dense_units[1], activation='relu',
                         kernel_regularizer=keras.regularizers.l2(self.l2_reg))(x)
        x = layers.Dropout(self.dropout_rate)(x)
        outputs = layers.Dense(1, activation='sigmoid')(x)
        self.model = models.Model(inputs=inputs, outputs=outputs)
        return self.model

    def _make_optimizer(self, name, lr):
        if name.lower() == 'adam':    return Adam(learning_rate=lr)
        if name.lower() == 'rmsprop': return RMSprop(learning_rate=lr)
        return SGD(learning_rate=lr, momentum=0.9)

    def _make_dataset(self, X, y, batch_size, augment=False):
        """tf.data pipeline; applies random rotation to training set only."""
        ds = tf.data.Dataset.from_tensor_slices(
            (tf.cast(X, tf.float32), tf.cast(y, tf.float32))
        )
        if augment:
            factor = CONFIG['augmentation_rotation'] / 360.0
            aug = tf.keras.Sequential([
                tf.keras.layers.RandomRotation(
                    factor=factor, fill_mode='nearest', seed=SEED)
            ])
            ds = ds.map(
                lambda x, lbl: (aug(x[tf.newaxis], training=True)[0], lbl),
                num_parallel_calls=tf.data.AUTOTUNE,
            )
        return ds.batch(batch_size).prefetch(tf.data.AUTOTUNE)

    def _class_weights(self, y):
        classes = np.unique(y)
        weights = compute_class_weight(class_weight='balanced', classes=classes, y=y)
        return dict(zip(classes.tolist(), weights.tolist()))

    def train_phase1(self, X_train, y_train, X_val=None, y_val=None, batch_size=32,
                     optimizer='adam', learning_rate=1e-3, max_epochs=100,
                     patience=5, verbose=1, fixed_epochs=None, save_checkpoint=True):
        self.model.compile(
            optimizer=self._make_optimizer(optimizer, learning_rate),
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.AUC(name='auc')],
            jit_compile=False,
        )
        train_ds = self._make_dataset(X_train, y_train, batch_size, augment=True)

        if fixed_epochs is not None:
            # Final retraining on full training set — no validation, no early stopping
            self.log(f"\n{'='*80}\nPHASE 1: Frozen Backbone "
                     f"[{fixed_epochs} epochs, full set] — {self.model_name}\n{'='*80}")
            self.log(f"Augmentation: rotation ±{CONFIG['augmentation_rotation']}°")
            self.phase1_history = self.model.fit(
                train_ds,
                epochs=fixed_epochs,
                class_weight=self._class_weights(y_train),
                verbose=verbose,
            )
            self.log(f"Phase 1 done (fixed {fixed_epochs} epochs).")
        else:
            self.log(f"\n{'='*80}\nPHASE 1: Frozen Backbone — {self.model_name}\n{'='*80}")
            self.log(f"Augmentation: rotation ±{CONFIG['augmentation_rotation']}°")
            val_ds = self._make_dataset(X_val, y_val, batch_size, augment=False)
            callbacks_p1 = [
                EarlyStopping(monitor='val_loss', patience=patience,
                              restore_best_weights=True, verbose=1),
            ]
            if save_checkpoint:
                ckpt = os.path.join(CONFIG['checkpoint_dir'],
                                    f"{self.model_name}_phase1_fold_best.h5")
                callbacks_p1.append(
                    ModelCheckpoint(ckpt, monitor='val_loss', save_best_only=True, verbose=0)
                )
            self.phase1_history = self.model.fit(
                train_ds, validation_data=val_ds,
                epochs=max_epochs,
                class_weight=self._class_weights(y_train),
                callbacks=callbacks_p1,
                verbose=verbose,
            )
            self.log(f"Phase 1 done. Best val_loss: "
                     f"{min(self.phase1_history.history['val_loss']):.6f}  "
                     f"(best epoch: {self.phase1_best_epoch})")

    def train_phase2(self, X_train, y_train, X_val=None, y_val=None, batch_size=32,
                     optimizer='adam', learning_rate=1e-4, max_epochs=100,
                     patience=15, verbose=1, fixed_epochs=None, save_checkpoint=True):
        n_layers = len(self.base_model.layers)
        unfreeze_from = int(n_layers * 0.7)
        for layer in self.base_model.layers[unfreeze_from:]:
            layer.trainable = True

        lr_schedule = ExponentialDecayScheduler(
            initial_lr=learning_rate,
            decay_rate=CONFIG['phase2_lr_decay'],
            decay_steps=CONFIG['phase2_decay_steps'],
        )
        self.model.compile(
            optimizer=self._make_optimizer(optimizer, lr_schedule),
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.AUC(name='auc')],
            jit_compile=False,
        )
        train_ds = self._make_dataset(X_train, y_train, batch_size, augment=True)

        if fixed_epochs is not None:
            # Final retraining on full training set — no validation, no early stopping
            self.log(f"\n{'='*80}\nPHASE 2: Fine-tuning "
                     f"[{fixed_epochs} epochs, full set] — {self.model_name}\n{'='*80}")
            self.log(f"Unfroze {n_layers - unfreeze_from} layers (from layer {unfreeze_from})")
            self.log(f"Augmentation: rotation ±{CONFIG['augmentation_rotation']}°")
            self.phase2_history = self.model.fit(
                train_ds,
                epochs=fixed_epochs,
                class_weight=self._class_weights(y_train),
                verbose=verbose,
            )
            self.log(f"Phase 2 done (fixed {fixed_epochs} epochs).")
        else:
            self.log(f"\n{'='*80}\nPHASE 2: Fine-tuning — {self.model_name}\n{'='*80}")
            self.log(f"Unfroze {n_layers - unfreeze_from} layers (from layer {unfreeze_from})")
            val_ds = self._make_dataset(X_val, y_val, batch_size, augment=False)
            callbacks_p2 = [
                EarlyStopping(monitor='val_loss', patience=patience,
                              restore_best_weights=True, verbose=1),
            ]
            if save_checkpoint:
                ckpt = os.path.join(CONFIG['checkpoint_dir'],
                                    f"{self.model_name}_phase2_fold_best.h5")
                callbacks_p2.append(
                    ModelCheckpoint(ckpt, monitor='val_loss', save_best_only=True, verbose=0)
                )
            self.phase2_history = self.model.fit(
                train_ds, validation_data=val_ds,
                epochs=max_epochs,
                class_weight=self._class_weights(y_train),
                callbacks=callbacks_p2,
                verbose=verbose,
            )
            self.log(f"Phase 2 done. Best val_loss: "
                     f"{min(self.phase2_history.history['val_loss']):.6f}  "
                     f"(best epoch: {self.phase2_best_epoch})")

    def get_predictions(self, X):
        return self.model.predict(X, verbose=0).flatten()

    def save_model(self, path):
        if path.endswith('.h5'):
            path = path.replace('.h5', '.keras')
        self.model.save(path)
        self.log(f"Model saved to {path}")


# ── Optuna ───────────────────────────────────────────────
class OptunaHyperparameterTuner:
    def __init__(self, model_name, base_model_fn, n_trials=50, log=print):
        self.model_name = model_name
        self.base_model_fn = base_model_fn
        self.n_trials = n_trials
        self.log = log
        self.best_params = None
        self.best_value = 0
        self.study = None

    def objective(self, trial, X_full, y_full, fold_indices):
        params = {
            'dropout_rate':  trial.suggest_float('dropout_rate', 0.2, 0.5),
            'l2_reg':        trial.suggest_float('l2_reg', 1e-5, 1e-2, log=True),
            'dense_units_1': trial.suggest_categorical('dense_units_1', [128, 256, 512]),
            'dense_units_2': trial.suggest_categorical('dense_units_2', [64, 128, 256]),
            'batch_size':    trial.suggest_categorical('batch_size', [16, 32]),
            'optimizer':     trial.suggest_categorical('optimizer', ['adam']),
            'phase1_lr':     trial.suggest_float('phase1_lr', 1e-4, 1e-2, log=True),
            'phase2_lr':     trial.suggest_float('phase2_lr', 1e-6, 1e-4, log=True),
        }
        try:
            fold = fold_indices[0]
            X_tr, y_tr = X_full[fold['train_idx']], y_full[fold['train_idx']]
            X_v,  y_v  = X_full[fold['val_idx']],   y_full[fold['val_idx']]

            base = self.base_model_fn()
            trainer = DFUModelTrainer(
                model_name=f"{self.model_name}_trial{trial.number}_fold1",
                base_model=base,
                dropout_rate=params['dropout_rate'],
                l2_reg=params['l2_reg'],
                dense_units=(params['dense_units_1'], params['dense_units_2']),
                log=self.log,
            )
            trainer.build_model()
            trainer.train_phase1(X_tr, y_tr, X_v, y_v,
                                 batch_size=params['batch_size'],
                                 optimizer=params['optimizer'],
                                 learning_rate=params['phase1_lr'],
                                 max_epochs=CONFIG['max_epochs'],
                                 patience=CONFIG['phase1_patience'],
                                 verbose=0, save_checkpoint=False)
            trainer.train_phase2(X_tr, y_tr, X_v, y_v,
                                 batch_size=params['batch_size'],
                                 optimizer=params['optimizer'],
                                 learning_rate=params['phase2_lr'],
                                 max_epochs=CONFIG['max_epochs'],
                                 patience=CONFIG['phase2_patience'],
                                 verbose=0, save_checkpoint=False)
            fold_auc = float(roc_auc_score(y_v, trainer.get_predictions(X_v)))
            del trainer, base
            tf.keras.backend.clear_session(); gc.collect()

            self.log(f"  Trial {trial.number}: fold1 AUC = {fold_auc:.4f}")
            return fold_auc
        except Exception as e:
            self.log(f"Trial {trial.number} failed: {e}")
            try:
                del trainer
            except Exception:
                pass
            try:
                del base
            except Exception:
                pass
            tf.keras.backend.clear_session(); gc.collect()
            return 0.0

    def optimize(self, X_full, y_full, fold_indices):
        self.log(f"\n{'='*80}\nOPTUNA: {self.model_name} ({self.n_trials} trials × fold1 only)\n{'='*80}")
        self.study = optuna.create_study(direction='maximize', sampler=TPESampler(seed=SEED))
        self.study.optimize(
            lambda t: self.objective(t, X_full, y_full, fold_indices),
            n_trials=self.n_trials, show_progress_bar=False,
        )
        self.best_params = self.study.best_params
        self.best_value = self.study.best_value
        self.log(f"\n✓ Best mean CV AUC: {self.best_value:.6f}")
        self.log(f"Best hyperparameters: {self.best_params}")
        tf.keras.backend.clear_session()
        gc.collect()
        return self.best_params


def compute_youden_threshold(y_true, y_pred):
    """Threshold that maximises Youden's J = Sensitivity + Specificity − 1."""
    fpr, tpr, thresholds = roc_curve(y_true, y_pred)
    j = tpr - fpr
    best = int(np.argmax(j))
    return float(thresholds[best]), float(tpr[best]), float(1.0 - fpr[best])


def find_best_fold(model_name: str, fold_indices: list, y_full) -> tuple:
    """Return (fold_index, val_auc) of the fold with highest validation AUC."""
    vp_path = os.path.join(CONFIG['checkpoint_dir'], f"{model_name}_val_preds.npz")
    npz = np.load(vp_path)
    best_idx, best_auc = 0, -1.0
    for i, fi in enumerate(fold_indices):
        yv = y_full[fi['val_idx']]
        vp = npz[f'fold{i+1}']
        a  = roc_auc_score(yv, vp)
        if a > best_auc:
            best_auc, best_idx = a, i
    return best_idx, float(best_auc)


def base_model_creators():
    return {
        'EfficientNetB0': lambda: efficientnet.EfficientNetB0(
            weights='imagenet', include_top=False, input_shape=(224, 224, 3)),
        'ResNet50':       lambda: resnet50.ResNet50(
            weights='imagenet', include_top=False, input_shape=(224, 224, 3)),
        'ConvNeXt-Tiny':  lambda: convnext.ConvNeXtTiny(
            weights='imagenet', include_top=False, input_shape=(224, 224, 3)),
    }


# ── Per-model training pipeline (used by train_*.py) ────
def train_one_model(model_name: str, base_model_fn, log):
    """Run Optuna + per-fold training for a single architecture. Resume-aware.
    Saves best_params JSON, fold checkpoints (.keras), and val predictions (.npz)."""
    log(f"\n{'#'*80}\n# TRAINING {model_name}\n{'#'*80}\n")

    images, labels = load_preprocessed_inaoe(CONFIG['data_source'], log=log)
    X_full, y_full = images, labels
    fold_indices, test_indices = create_fold_splits(
        X_full, y_full, n_splits=CONFIG['n_folds'],
        test_split=CONFIG['test_split'], random_state=SEED,
    )
    log(f"✓ {len(fold_indices)} folds  |  test set: {len(test_indices)}")

    ckpt_dir = CONFIG['checkpoint_dir']
    bp_path = os.path.join(ckpt_dir, f"{model_name}_best_params.json")
    fold_ckpts = [os.path.join(ckpt_dir, f"{model_name}_Fold{i+1}_final.keras")
                  for i in range(CONFIG['n_folds'])]
    val_preds_path = os.path.join(ckpt_dir, f"{model_name}_val_preds.npz")

    # ── Step 1: Optuna ──
    if os.path.exists(bp_path):
        with open(bp_path) as f:
            best_params = json.load(f)
        log(f"✓ Loaded best_params — skipping Optuna")
    else:
        tuner = OptunaHyperparameterTuner(
            model_name=f"{model_name}_HyperparameterSearch",
            base_model_fn=base_model_fn,
            n_trials=CONFIG['optuna_trials'],
            log=log,
        )
        best_params = tuner.optimize(X_full, y_full, fold_indices)
        with open(bp_path, 'w') as f:
            json.dump(best_params, f, indent=2)
        log(f"✓ best_params → {bp_path}")

    # ── Step 2: Per-fold training ──
    fold_val_preds = {}
    fold_epochs    = {}   # {fold_key: {phase1: int, phase2: int}} — fresh folds only
    for fold_num, fold in enumerate(fold_indices):
        ckpt = fold_ckpts[fold_num]
        X_v = X_full[fold['val_idx']]
        y_v = y_full[fold['val_idx']]

        if os.path.exists(ckpt):
            log(f"✓ Fold {fold_num+1}: loading existing checkpoint")
            m = tf.keras.models.load_model(ckpt)
            preds = m.predict(X_v, verbose=0).flatten()
            del m
            tf.keras.backend.clear_session(); gc.collect()
        else:
            log(f"\n{'='*80}\nFOLD {fold_num+1}/{len(fold_indices)}: {model_name}\n{'='*80}")
            X_tr, y_tr = X_full[fold['train_idx']], y_full[fold['train_idx']]
            log(f"Train: {len(X_tr)}  |  Val: {len(X_v)}")
            base = base_model_fn()
            trainer = DFUModelTrainer(
                model_name=f"{model_name}_Fold{fold_num+1}",
                base_model=base,
                dropout_rate=best_params['dropout_rate'],
                l2_reg=best_params['l2_reg'],
                dense_units=(best_params['dense_units_1'], best_params['dense_units_2']),
                log=log,
            )
            trainer.build_model()
            trainer.train_phase1(X_tr, y_tr, X_v, y_v,
                                 batch_size=best_params['batch_size'],
                                 optimizer=best_params['optimizer'],
                                 learning_rate=best_params['phase1_lr'],
                                 max_epochs=CONFIG['max_epochs'],
                                 patience=CONFIG['phase1_patience'],
                                 verbose=1)
            trainer.train_phase2(X_tr, y_tr, X_v, y_v,
                                 batch_size=best_params['batch_size'],
                                 optimizer=best_params['optimizer'],
                                 learning_rate=best_params['phase2_lr'],
                                 max_epochs=CONFIG['max_epochs'],
                                 patience=CONFIG['phase2_patience'],
                                 verbose=1)
            preds = trainer.get_predictions(X_v)
            trainer.save_model(ckpt)
            # Record best stopping epochs for final-retrain computation
            fold_key = f'fold{fold_num+1}'
            fold_epochs[fold_key] = {
                'phase1': trainer.phase1_best_epoch,
                'phase2': trainer.phase2_best_epoch,
            }
            log(f"✓ Fold {fold_num+1} complete  "
                f"(best epoch: phase1={trainer.phase1_best_epoch}, "
                f"phase2={trainer.phase2_best_epoch})")
            del trainer, base
            tf.keras.backend.clear_session(); gc.collect()

        fold_val_preds[f'fold{fold_num+1}'] = preds

    # Save val predictions for evaluate.py
    np.savez(val_preds_path, **fold_val_preds)
    log(f"✓ Val predictions → {val_preds_path}")

    # Save average stopping epochs (used by final_evaluation for retraining)
    avg_epochs_path = os.path.join(ckpt_dir, f"{model_name}_avg_epochs.json")
    if fold_epochs:
        # Merge with existing per_fold data so partial re-runs accumulate correctly
        merged = {}
        if os.path.exists(avg_epochs_path):
            with open(avg_epochs_path) as _f:
                _existing = json.load(_f)
            merged = _existing.get('per_fold', {})
        merged.update(fold_epochs)  # new data overwrites same-key entries

        p1_epochs = [v['phase1'] for v in merged.values() if v.get('phase1') is not None]
        p2_epochs = [v['phase2'] for v in merged.values() if v.get('phase2') is not None]
        avg_p1 = int(round(np.mean(p1_epochs))) if p1_epochs else None
        avg_p2 = int(round(np.mean(p2_epochs))) if p2_epochs else None
        epochs_data = {
            'per_fold':     merged,
            'avg_phase1':   avg_p1,
            'avg_phase2':   avg_p2,
            'n_folds_used': len(merged),
        }
        with open(avg_epochs_path, 'w') as f:
            json.dump(epochs_data, f, indent=2)
        log(f"✓ Avg stopping epochs (phase1={avg_p1}, phase2={avg_p2}, "
            f"from {len(merged)} folds) → {avg_epochs_path}")
    elif not os.path.exists(avg_epochs_path):
        log(f"⚠ All folds loaded from checkpoint — {avg_epochs_path} not written. "
            f"Delete fold checkpoints and re-run to regenerate it.")

    # ── Summary ──
    log(f"\n{'─'*60}\n  {model_name} — Validation Metrics Per Fold\n{'─'*60}")
    aucs, sens_l, spec_l = [], [], []
    for i, fold in enumerate(fold_indices):
        yv = y_full[fold['val_idx']]
        vp = fold_val_preds[f'fold{i+1}']
        a = roc_auc_score(yv, vp)
        yb = (vp >= 0.5).astype(int)
        tp = int(np.sum((yb == 1) & (yv == 1)))
        fp = int(np.sum((yb == 1) & (yv == 0)))
        fn = int(np.sum((yb == 0) & (yv == 1)))
        tn = int(np.sum((yb == 0) & (yv == 0)))
        s = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        sp = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        aucs.append(a); sens_l.append(s); spec_l.append(sp)
        log(f"  Fold {i+1}:  AUC={a:.4f}  Sens={s:.4f}  Spec={sp:.4f}")
    log(f"  Mean :  AUC={np.mean(aucs):.4f}  Sens={np.mean(sens_l):.4f}  Spec={np.mean(spec_l):.4f}")
    log(f"\n{'#'*80}\n# {model_name} TRAINING COMPLETE\n{'#'*80}\n")
