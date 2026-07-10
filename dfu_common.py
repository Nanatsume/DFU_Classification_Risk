"""Shared code for DFU training pipeline (config, data, models, trainer, tuner)."""

import os
import sys
import warnings
import json
import gc
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Disable XLA JIT compilation — RTX 5060 Ti (compute cap 12.0a) is not natively
# supported by this TF build and PTX JIT-compilation hangs indefinitely.
os.environ['TF_XLA_FLAGS'] = '--tf_xla_auto_jit=0'
os.environ['XLA_FLAGS'] = '--xla_disable_hlo_passes=all'

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedKFold
from sklearn.utils.class_weight import compute_class_weight
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_curve, auc, roc_auc_score, classification_report
)

import tensorflow as tf

# Force jit_compile=False globally — ConvNeXt uses @tf.function(jit_compile=True)
# internally which triggers XLA PTX compilation that hangs on RTX 5060 Ti.
_orig_tf_function = tf.function
def _tf_function_no_jit(func=None, **kwargs):
    kwargs['jit_compile'] = False
    if func is not None:
        return _orig_tf_function(func, **kwargs)
    return lambda f: _orig_tf_function(f, **kwargs)
tf.function = _tf_function_no_jit

from tensorflow import keras
from tensorflow.keras import layers, models
from tensorflow.keras.optimizers import Adam, RMSprop, SGD
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
from tensorflow.keras.applications import efficientnet, resnet50, convnext

import GPyOpt

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
    'data_source':         '/home/ntphoto/DFU/INAOE_S1',
    'checkpoint_dir':      './model_checkpoints',
    'results_dir':         './results',
    'img_size':            (224, 224),
    'batch_size_default':  64,
    'max_epochs':          50,
    'phase1_patience':     5,
    'phase2_patience':     5,
    'n_folds':             5,
    'test_split':          0.2,
    'n_bo_trials':         10,
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


def create_patient_fold_splits(image_paths, labels, patient_ids,
                                n_splits=5, test_split=0.2, random_state=SEED):
    """
    Patient-level stratified k-fold split for podoscope data.

    Prevents data leakage by ensuring both feet of the same patient
    (e.g. P001_L and P001_R) always stay in the same fold.

    Patient-level label: 1 if ANY foot of that patient is positive (DM),
    0 if all feet are negative (CT).

    Parameters
    ----------
    image_paths : list of str
    labels      : array-like of int  (0=CT, 1=DM, per image)
    patient_ids : list of str  (e.g. ['P001', 'P001', 'P002', ...])
    n_splits    : int   — number of CV folds (default 5)
    test_split  : float — fraction held out as test set (default 0.2)
    random_state: int

    Returns
    -------
    fold_indices : list of dicts, each with keys 'fold', 'train_idx', 'val_idx'
    test_indices : np.ndarray of int indices into image_paths / labels
    """
    from sklearn.model_selection import StratifiedGroupKFold

    image_paths = list(image_paths)
    labels      = np.array(labels, dtype=np.int32)
    patient_ids = list(patient_ids)

    unique_patients = sorted(set(patient_ids))
    pid_to_idx = {p: i for i, p in enumerate(unique_patients)}
    groups = np.array([pid_to_idx[p] for p in patient_ids], dtype=np.int32)

    # Patient-level label: positive if any image of that patient is DM
    patient_label = {}
    for pid, lbl in zip(patient_ids, labels):
        patient_label[pid] = max(patient_label.get(pid, 0), int(lbl))
    image_patient_label = np.array([patient_label[p] for p in patient_ids], dtype=np.int32)

    # 80/20 patient-level test split
    n_test_folds = max(2, int(round(1.0 / test_split)))
    sgkf_test = StratifiedGroupKFold(n_splits=n_test_folds, shuffle=True,
                                     random_state=random_state)
    train_val_idx, test_indices = next(
        iter(sgkf_test.split(labels, image_patient_label, groups=groups))
    )

    # 5-fold CV on the remaining train/val pool
    sgkf_cv = StratifiedGroupKFold(n_splits=n_splits, shuffle=True,
                                   random_state=random_state)
    fold_indices = []
    tv_labels = image_patient_label[train_val_idx]
    tv_groups = groups[train_val_idx]
    for fi, (tr, vl) in enumerate(sgkf_cv.split(
            train_val_idx, tv_labels, groups=tv_groups)):
        fold_indices.append({
            'fold':      fi,
            'train_idx': train_val_idx[tr],
            'val_idx':   train_val_idx[vl],
        })

    print(f"Patient-level split: {len(unique_patients)} patients, "
          f"test={len(test_indices)} images, "
          f"train/val pool={len(train_val_idx)} images")
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
                 dense_units=(256, 64), log=print, backbone_name=None):
        self.model_name   = model_name
        self.base_model   = base_model
        self.dropout_rate = dropout_rate
        self.l2_reg       = l2_reg
        self.dense_units  = dense_units
        self.log          = log
        self.backbone_name = backbone_name or model_name.split('_')[0]
        self.model        = None
        self.phase1_history = None
        self.phase2_history = None
        self._epoch_used   = {'phase1': None, 'phase2': None}

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
        # Backbones expect [0,255]; scale from stored [0,1]
        x = layers.Rescaling(255.0)(inputs)
        # ResNet50 has no built-in preprocessing: apply caffe-style mean subtraction
        if self.model_name == 'ResNet50':
            x = layers.Lambda(lambda t: resnet50.preprocess_input(t))(x)
        x = self.base_model(x, training=False)
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
        X_f32 = X if X.dtype == np.float32 else X.astype(np.float32)
        y_f32 = y.astype(np.float32)
        ds = tf.data.Dataset.from_tensor_slices((X_f32, y_f32))
        if augment:
            if not hasattr(self, '_aug'):
                factor = CONFIG['augmentation_rotation'] / 360.0
                self._aug = tf.keras.Sequential([
                    tf.keras.layers.RandomRotation(
                        factor=factor, fill_mode='nearest', seed=SEED)
                ])
            aug = self._aug
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
        for layer in self.base_model.layers:
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
            self.log(f"Unfroze all {n_layers} backbone layers (Full Fine-tuning)")
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
            self.log(f"Unfroze all {n_layers} backbone layers (Full Fine-tuning)")
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

    def get_epochs(self) -> dict:
        """Return stopping epoch counts for the most recent train_with_strategy() call."""
        p1 = self._epoch_used.get('phase1')
        if p1 is None and self.phase1_history is not None:
            p1 = len(self.phase1_history.history.get('val_loss', []))
        p2 = self._epoch_used.get('phase2')
        if p2 is None and self.phase2_history is not None:
            p2 = len(self.phase2_history.history.get('val_loss', []))
        return {'phase1': p1, 'phase2': p2}

    def retrain_fixed(self, strategy: str, X_tr, y_tr, params: dict,
                      epochs_p1: int, epochs_p2: int = 0, verbose: int = 1):
        """Retrain on full training set for exactly epochs_p1 (and epochs_p2 for LP-FT).
        No validation data, no early stopping — for final model training after CV."""
        batch_size = params.get('batch_size', CONFIG['batch_size_default'])
        cw = self._class_weights(y_tr)
        train_ds = self._make_dataset(X_tr, y_tr, batch_size, augment=True)

        if strategy == 'LP-FT':
            self.train_phase1(X_tr, y_tr, batch_size=batch_size, optimizer=params['optimizer'],
                              learning_rate=params['phase1_lr'], fixed_epochs=epochs_p1,
                              verbose=verbose)
            self.train_phase2(X_tr, y_tr, batch_size=batch_size, optimizer=params['optimizer'],
                              learning_rate=params['phase2_lr'], fixed_epochs=epochs_p2,
                              verbose=verbose)
            return

        if strategy == 'FT':
            for layer in self.base_model.layers:
                layer.trainable = True
            lr = params['lr']
        elif strategy == 'LP':
            lr = params['lr']
        elif strategy in ('G-LF', 'G-FL'):
            self._retrain_gradual_fixed(X_tr, y_tr, params, epochs_p1, verbose,
                                        reverse=(strategy == 'G-LF'))
            return
        elif strategy in ('L1-SP', 'L2-SP'):
            self._retrain_sp_fixed(X_tr, y_tr, params, epochs_p1, verbose,
                                   sp_type='l1' if strategy == 'L1-SP' else 'l2')
            return
        elif strategy == 'Auto-RGN':
            self._retrain_auto_rgn_fixed(X_tr, y_tr, params, epochs_p1, verbose)
            return
        else:
            raise ValueError(f'Unknown strategy for retrain_fixed: {strategy}')

        self.model.compile(
            optimizer=self._make_optimizer(params['optimizer'], lr),
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.AUC(name='auc')], jit_compile=False,
        )
        self.phase1_history = self.model.fit(
            train_ds, epochs=epochs_p1, class_weight=cw, verbose=verbose,
        )

    def _retrain_gradual_fixed(self, X_tr, y_tr, params, total_epochs, verbose, reverse):
        name = 'G-LF' if reverse else 'G-FL'
        self.log(f"\n{'='*80}\n{name} FIXED RETRAIN — {self.model_name}\n{'='*80}")
        blocks  = get_backbone_blocks(self.backbone_name, self.base_model)
        ordered = blocks[::-1] if reverse else blocks
        epochs_per_block = max(1, total_epochs // len(ordered))
        for layer in self.base_model.layers:
            layer.trainable = False
        train_ds = self._make_dataset(X_tr, y_tr, params['batch_size'], augment=True)
        cw = self._class_weights(y_tr)
        used = 0
        for bi, block in enumerate(ordered):
            for layer in block:
                layer.trainable = True
            n = min(epochs_per_block, total_epochs - used)
            if n <= 0:
                break
            self.model.compile(
                optimizer=self._make_optimizer(params['optimizer'], params['lr']),
                loss='binary_crossentropy',
                metrics=['accuracy', tf.keras.metrics.AUC(name='auc')], jit_compile=False,
            )
            self.log(f"  Block {bi+1}/{len(ordered)}: {n} epochs (fixed)")
            h = self.model.fit(train_ds, epochs=n, class_weight=cw, verbose=verbose)
            used += n
            self.phase1_history = h
            if used >= total_epochs:
                break
        self.log(f"  {name} fixed retrain done. Total epochs: {used}")

    def _retrain_sp_fixed(self, X_tr, y_tr, params, total_epochs, verbose, sp_type):
        name = 'L1-SP' if sp_type == 'l1' else 'L2-SP'
        self.log(f"\n{'='*80}\n{name} FIXED RETRAIN — {self.model_name}\n{'='*80}")
        for layer in self.base_model.layers:
            layer.trainable = True
        backbone_vars = [v for l in self.base_model.layers for v in l.trainable_weights]
        pretrained    = [tf.constant(v.numpy()) for v in backbone_vars]
        bb_ids        = {id(v) for v in backbone_vars}
        head_vars     = [v for v in self.model.trainable_weights if id(v) not in bb_ids]
        all_vars      = backbone_vars + head_vars
        alpha, beta   = params['alpha'], params['beta']
        opt           = tf.keras.optimizers.Adam(learning_rate=params['lr'])
        bce           = tf.keras.losses.BinaryCrossentropy()
        cw            = self._class_weights(y_tr)
        cw_t          = tf.constant([cw[0], cw[1]], dtype=tf.float32)
        bs = min(params['batch_size'], 16)  # L1/L2-SP holds pretrained weight constants and computes penalty inside GradientTape
        train_ds = self._make_dataset(X_tr, y_tr, bs, augment=True)
        for epoch in range(total_epochs):
            for xb, yb in train_ds:
                with tf.GradientTape() as tape:
                    p  = self.model(xb, training=True)
                    sw = tf.gather(cw_t, tf.cast(yb, tf.int32))
                    ce = bce(yb[:, tf.newaxis], p, sample_weight=sw)
                    if sp_type == 'l1':
                        sp = tf.add_n([tf.reduce_sum(tf.abs(v - v0)) for v, v0 in zip(backbone_vars, pretrained)])
                        hp = tf.add_n([tf.reduce_sum(tf.abs(v)) for v in head_vars]) if head_vars else 0.0
                    else:
                        sp = tf.add_n([tf.reduce_sum(tf.square(v - v0)) for v, v0 in zip(backbone_vars, pretrained)])
                        hp = tf.add_n([tf.reduce_sum(tf.square(v)) for v in head_vars]) if head_vars else 0.0
                    loss = ce + alpha * sp + beta * hp
                opt.apply_gradients(zip(tape.gradient(loss, all_vars), all_vars))
            if verbose and (epoch + 1) % 5 == 0:
                self.log(f"  Epoch {epoch+1}/{total_epochs}")
        self.log(f"  {name} fixed retrain done.")

    def _retrain_auto_rgn_fixed(self, X_tr, y_tr, params, total_epochs, verbose):
        self.log(f"\n{'='*80}\nAuto-RGN FIXED RETRAIN — {self.model_name}\n{'='*80}")
        for layer in self.base_model.layers:
            layer.trainable = True
        all_vars  = self.model.trainable_weights
        base_lr   = params['lr']
        bce       = tf.keras.losses.BinaryCrossentropy()
        cw        = self._class_weights(y_tr)
        cw_t      = tf.constant([cw[0], cw[1]], dtype=tf.float32)
        train_ds  = self._make_dataset(X_tr, y_tr, params['batch_size'], augment=True)
        for epoch in range(total_epochs):
            for xb, yb in train_ds:
                with tf.GradientTape() as tape:
                    p  = self.model(xb, training=True)
                    sw = tf.gather(cw_t, tf.cast(yb, tf.int32))
                    loss = bce(yb[:, tf.newaxis], p, sample_weight=sw)
                grads = tape.gradient(loss, all_vars)
                rgns  = [tf.norm(g) / (tf.norm(v) + 1e-8) if g is not None else tf.constant(0.0)
                         for g, v in zip(grads, all_vars)]
                mean_rgn = tf.reduce_mean(tf.stack(rgns)) + 1e-8
                for g, v, r in zip(grads, all_vars, rgns):
                    if g is not None:
                        v.assign_sub(base_lr * (r / mean_rgn) * g)
            if verbose and (epoch + 1) % 5 == 0:
                self.log(f"  Epoch {epoch+1}/{total_epochs}")
        self.log(f"  Auto-RGN fixed retrain done.")

    # ── Strategy dispatcher ───────────────────────────────
    def train_with_strategy(self, strategy: str, X_tr, y_tr, X_val, y_val,
                             params: dict, max_epochs=50, patience=5, verbose=1):
        self._epoch_used = {'phase1': None, 'phase2': None}
        if strategy == 'LP-FT':
            self.train_phase1(X_tr, y_tr, X_val, y_val,
                              batch_size=params['batch_size'], optimizer=params['optimizer'],
                              learning_rate=params['phase1_lr'], max_epochs=max_epochs,
                              patience=patience, verbose=verbose)
            self.train_phase2(X_tr, y_tr, X_val, y_val,
                              batch_size=params['batch_size'], optimizer=params['optimizer'],
                              learning_rate=params['phase2_lr'], max_epochs=max_epochs,
                              patience=patience * 3, verbose=verbose)
        elif strategy == 'FT':
            self._train_ft(X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose)
        elif strategy == 'LP':
            self._train_lp(X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose)
        elif strategy == 'G-LF':
            self._train_gradual(X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose, reverse=True)
        elif strategy == 'G-FL':
            self._train_gradual(X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose, reverse=False)
        elif strategy in ('L1-SP', 'L2-SP'):
            self._train_sp(X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose,
                           sp_type='l1' if strategy == 'L1-SP' else 'l2')
        elif strategy == 'Auto-RGN':
            self._train_auto_rgn(X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose)
        else:
            raise ValueError(f'Unknown strategy: {strategy}')

    def _train_ft(self, X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose):
        for layer in self.base_model.layers:
            layer.trainable = True
        self.model.compile(
            optimizer=self._make_optimizer(params['optimizer'], params['lr']),
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.AUC(name='auc')], jit_compile=False,
        )
        train_ds = self._make_dataset(X_tr, y_tr, params['batch_size'], augment=True)
        val_ds   = self._make_dataset(X_val, y_val, params['batch_size'], augment=False)
        cb = [EarlyStopping(monitor='val_loss', patience=patience, restore_best_weights=True, verbose=1)]
        self.log(f"\n{'='*80}\nFULL FINE-TUNING (FT) — {self.model_name}\n{'='*80}")
        self.phase1_history = self.model.fit(
            train_ds, validation_data=val_ds, epochs=max_epochs,
            class_weight=self._class_weights(y_tr), callbacks=cb, verbose=verbose,
        )

    def _train_lp(self, X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose):
        self.model.compile(
            optimizer=self._make_optimizer(params['optimizer'], params['lr']),
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.AUC(name='auc')], jit_compile=False,
        )
        train_ds = self._make_dataset(X_tr, y_tr, params['batch_size'], augment=True)
        val_ds   = self._make_dataset(X_val, y_val, params['batch_size'], augment=False)
        cb = [EarlyStopping(monitor='val_loss', patience=patience, restore_best_weights=True, verbose=1)]
        self.log(f"\n{'='*80}\nLINEAR PROBING (LP) — {self.model_name}\n{'='*80}")
        self.phase1_history = self.model.fit(
            train_ds, validation_data=val_ds, epochs=max_epochs,
            class_weight=self._class_weights(y_tr), callbacks=cb, verbose=verbose,
        )

    def _train_gradual(self, X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose, reverse: bool):
        name = 'G-LF' if reverse else 'G-FL'
        self.log(f"\n{'='*80}\n{name} — {self.model_name}\n{'='*80}")
        blocks  = get_backbone_blocks(self.backbone_name, self.base_model)
        ordered = blocks[::-1] if reverse else blocks
        epochs_per_block = max(1, max_epochs // len(ordered))
        for layer in self.base_model.layers:
            layer.trainable = False
        train_ds = self._make_dataset(X_tr, y_tr, params['batch_size'], augment=True)
        val_ds   = self._make_dataset(X_val, y_val, params['batch_size'], augment=False)
        cw = self._class_weights(y_tr)
        used = 0
        for bi, block in enumerate(ordered):
            for layer in block:
                layer.trainable = True
            n = min(epochs_per_block, max_epochs - used)
            if n <= 0:
                break
            self.model.compile(
                optimizer=self._make_optimizer(params['optimizer'], params['lr']),
                loss='binary_crossentropy',
                metrics=['accuracy', tf.keras.metrics.AUC(name='auc')], jit_compile=False,
            )
            cb = [EarlyStopping(monitor='val_loss', patience=patience, restore_best_weights=True, verbose=0)]
            self.log(f"  Block {bi+1}/{len(ordered)}: unfreezing {len(block)} layers, budget {n} epochs")
            h = self.model.fit(train_ds, validation_data=val_ds, epochs=n,
                               class_weight=cw, callbacks=cb, verbose=verbose)
            used += len(h.history['val_loss'])
            self.phase1_history = h
            del cb, h
            gc.collect()
            if used >= max_epochs:
                break
        self.log(f"  {name} done. Total epochs used: {used}")
        self._epoch_used['phase1'] = used

    def _sp_custom_loop(self, X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose, sp_type):
        for layer in self.base_model.layers:
            layer.trainable = True
        backbone_vars  = [v for l in self.base_model.layers for v in l.trainable_weights]
        pretrained     = [tf.constant(v.numpy()) for v in backbone_vars]
        bb_ids         = {id(v) for v in backbone_vars}
        head_vars      = [v for v in self.model.trainable_weights if id(v) not in bb_ids]
        all_vars       = backbone_vars + head_vars
        alpha, beta    = params['alpha'], params['beta']
        opt            = tf.keras.optimizers.Adam(learning_rate=params['lr'])
        bce            = tf.keras.losses.BinaryCrossentropy()
        cw             = self._class_weights(y_tr)
        cw_t           = tf.constant([cw[0], cw[1]], dtype=tf.float32)
        bs = min(params['batch_size'], 16)  # L1/L2-SP holds pretrained weight constants and computes penalty inside GradientTape
        train_ds = self._make_dataset(X_tr, y_tr, bs, augment=True)
        val_ds   = self._make_dataset(X_val, y_val, bs, augment=False)
        best_loss, patience_cnt, best_w = float('inf'), 0, None
        for epoch in range(max_epochs):
            for xb, yb in train_ds:
                with tf.GradientTape() as tape:
                    p  = self.model(xb, training=True)
                    sw = tf.gather(cw_t, tf.cast(yb, tf.int32))
                    ce = bce(yb[:, tf.newaxis], p, sample_weight=sw)
                    if sp_type == 'l1':
                        sp = tf.add_n([tf.reduce_sum(tf.abs(v - v0)) for v, v0 in zip(backbone_vars, pretrained)])
                        hp = tf.add_n([tf.reduce_sum(tf.abs(v)) for v in head_vars]) if head_vars else 0.0
                    else:
                        sp = tf.add_n([tf.reduce_sum(tf.square(v - v0)) for v, v0 in zip(backbone_vars, pretrained)])
                        hp = tf.add_n([tf.reduce_sum(tf.square(v)) for v in head_vars]) if head_vars else 0.0
                    loss = ce + alpha * sp + beta * hp
                opt.apply_gradients(zip(tape.gradient(loss, all_vars), all_vars))
            vl = float(np.mean([
                float(bce(yb[:, tf.newaxis], self.model(xb, training=False),
                          sample_weight=tf.gather(cw_t, tf.cast(yb, tf.int32))))
                for xb, yb in val_ds
            ]))
            if verbose and (epoch + 1) % 5 == 0:
                self.log(f"  Epoch {epoch+1}/{max_epochs}  val_loss={vl:.4f}")
            if vl < best_loss:
                best_loss, patience_cnt = vl, 0
                best_w = [v.numpy() for v in self.model.weights]
            else:
                patience_cnt += 1
                if patience_cnt >= patience:
                    self.log(f"  Early stopping at epoch {epoch+1}")
                    break
        if best_w:
            for var, val in zip(self.model.weights, best_w):
                var.assign(val)
        self._epoch_used['phase1'] = epoch + 1
        self.log(f"  Best val_loss: {best_loss:.6f}")

    def _train_sp(self, X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose, sp_type):
        name = 'L1-SP' if sp_type == 'l1' else 'L2-SP'
        self.log(f"\n{'='*80}\n{name} — {self.model_name}\n{'='*80}")
        self._sp_custom_loop(X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose, sp_type)

    def _train_auto_rgn(self, X_tr, y_tr, X_val, y_val, params, max_epochs, patience, verbose):
        self.log(f"\n{'='*80}\nAuto-RGN — {self.model_name}\n{'='*80}")
        for layer in self.base_model.layers:
            layer.trainable = True
        all_vars  = self.model.trainable_weights
        base_lr   = params['lr']
        bce       = tf.keras.losses.BinaryCrossentropy()
        cw        = self._class_weights(y_tr)
        cw_t      = tf.constant([cw[0], cw[1]], dtype=tf.float32)
        bs = min(params['batch_size'], 8)  # Auto-RGN holds all layer gradients in memory at once
        train_ds  = self._make_dataset(X_tr, y_tr, bs, augment=True)
        val_ds    = self._make_dataset(X_val, y_val, bs, augment=False)
        best_loss, patience_cnt, best_w = float('inf'), 0, None
        for epoch in range(max_epochs):
            for xb, yb in train_ds:
                with tf.GradientTape() as tape:
                    p  = self.model(xb, training=True)
                    sw = tf.gather(cw_t, tf.cast(yb, tf.int32))
                    loss = bce(yb[:, tf.newaxis], p, sample_weight=sw)
                grads = tape.gradient(loss, all_vars)
                rgns  = [tf.norm(g) / (tf.norm(v) + 1e-8) if g is not None else tf.constant(0.0)
                         for g, v in zip(grads, all_vars)]
                mean_rgn = tf.reduce_mean(tf.stack(rgns)) + 1e-8
                for g, v, r in zip(grads, all_vars, rgns):
                    if g is not None:
                        v.assign_sub(base_lr * (r / mean_rgn) * g)
            vl = float(np.mean([
                float(bce(yb[:, tf.newaxis], self.model(xb, training=False),
                          sample_weight=tf.gather(cw_t, tf.cast(yb, tf.int32))))
                for xb, yb in val_ds
            ]))
            if verbose and (epoch + 1) % 5 == 0:
                self.log(f"  Epoch {epoch+1}/{max_epochs}  val_loss={vl:.4f}")
            if vl < best_loss:
                best_loss, patience_cnt = vl, 0
                best_w = [v.numpy() for v in self.model.weights]
            else:
                patience_cnt += 1
                if patience_cnt >= patience:
                    self.log(f"  Early stopping at epoch {epoch+1}")
                    break
        if best_w:
            for var, val in zip(self.model.weights, best_w):
                var.assign(val)
        self._epoch_used['phase1'] = epoch + 1
        self.log(f"  Best val_loss: {best_loss:.6f}")


# ── GPyOpt ───────────────────────────────────────────────
_DENSE1_CHOICES = [128, 256, 512]
_DENSE2_CHOICES = [32, 64, 128]

_GPYOPT_DOMAIN = [
    {'name': 'dropout_rate',   'type': 'continuous', 'domain': (0.1, 0.4)},
    {'name': 'l2_reg_log',     'type': 'continuous', 'domain': (np.log10(1e-6), np.log10(1e-1))},
    {'name': 'dense_units_1',  'type': 'discrete',   'domain': (0, 1, 2)},
    {'name': 'dense_units_2',  'type': 'discrete',   'domain': (0, 1, 2)},
    {'name': 'phase1_lr_log',  'type': 'continuous', 'domain': (np.log10(1e-4), np.log10(1e-2))},
    {'name': 'phase2_lr_log',  'type': 'continuous', 'domain': (np.log10(1e-6), np.log10(1e-4))},
]


def _decode_gpyopt_x(x):
    """Convert GPyOpt flat array to named hyperparameter dict."""
    return {
        'dropout_rate':  float(x[0]),
        'l2_reg':        float(10 ** x[1]),
        'dense_units_1': _DENSE1_CHOICES[int(round(x[2]))],
        'dense_units_2': _DENSE2_CHOICES[int(round(x[3]))],
        'batch_size':    CONFIG['batch_size_default'],
        'optimizer':     'adam',
        'phase1_lr':     float(10 ** x[4]),
        'phase2_lr':     float(10 ** x[5]),
    }


class GPyOptHyperparameterTuner:
    def __init__(self, model_name, base_model_fn, n_trials=10, log=print):
        self.model_name   = model_name
        self.base_model_fn = base_model_fn
        self.n_trials     = n_trials
        self.log          = log
        self.best_params  = None
        self.best_value   = 0.0
        self._trial_num   = 0

    def _evaluate(self, X_gpyopt, X_full, y_full, fold_indices):
        """Called by GPyOpt with a (1 × 6) array; returns (1 × 1) cost (negated AUC)."""
        x      = X_gpyopt[0]
        params = _decode_gpyopt_x(x)
        self._trial_num += 1
        trial_id = self._trial_num

        fold   = fold_indices[0]
        X_tr, y_tr = X_full[fold['train_idx']], y_full[fold['train_idx']]
        X_v,  y_v  = X_full[fold['val_idx']],   y_full[fold['val_idx']]
        try:
            base = self.base_model_fn()
            trainer = DFUModelTrainer(
                model_name=f"{self.model_name}_trial{trial_id}_fold1",
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
            self.log(f"  Trial {trial_id}: fold1 AUC = {fold_auc:.4f}  params={params}")
            return np.array([[- fold_auc]])   # GPyOpt minimises
        except Exception as e:
            self.log(f"Trial {trial_id} failed: {e}")
            try: del trainer
            except Exception: pass
            try: del base
            except Exception: pass
            tf.keras.backend.clear_session(); gc.collect()
            return np.array([[0.0]])

    def optimize(self, X_full, y_full, fold_indices):
        self.log(f"\n{'='*80}\nGPyOpt: {self.model_name} ({self.n_trials} trials × fold1 only)\n{'='*80}")
        bo = GPyOpt.methods.BayesianOptimization(
            f=lambda x: self._evaluate(x, X_full, y_full, fold_indices),
            domain=_GPYOPT_DOMAIN,
            model_type='GP',
            acquisition_type='EI',
            exact_feval=False,
            maximize=False,
            verbosity=False,
            initial_design_numdata=1,   # 1 random init + (n_trials-1) BO = n_trials total
        )
        bo.run_optimization(max_iter=self.n_trials - 1)
        best_x = bo.x_opt
        self.best_params = _decode_gpyopt_x(best_x)
        self.best_value  = float(-bo.fx_opt)
        self.log(f"\n✓ Best fold1 AUC: {self.best_value:.6f}")
        self.log(f"Best hyperparameters: {self.best_params}")
        tf.keras.backend.clear_session(); gc.collect()
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
        tuner = GPyOptHyperparameterTuner(
            model_name=f"{model_name}_HyperparameterSearch",
            base_model_fn=base_model_fn,
            n_trials=CONFIG['n_bo_trials'],
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


# ── 8 Fine-Tuning Strategy support ───────────────────────────────────────────

ALL_STRATEGIES = ['FT', 'LP', 'G-LF', 'G-FL', 'LP-FT', 'L1-SP', 'L2-SP', 'Auto-RGN']

_BACKBONE_BLOCKS = {
    'EfficientNetB0': [
        ['stem_'],
        ['block1', 'block2'],
        ['block3', 'block4'],
        ['block5', 'block6'],
        ['block7', 'top_'],
    ],
    'ResNet50': [
        ['conv1_', 'bn_conv1', 'conv1_pad'],
        ['conv2_'], ['conv3_'], ['conv4_'], ['conv5_'],
    ],
    'ConvNeXt-Tiny': [
        ['convnext_tiny_stem'],
        ['convnext_tiny_downsampling_block_0', 'convnext_tiny_stage_0'],
        ['convnext_tiny_downsampling_block_1', 'convnext_tiny_stage_1'],
        ['convnext_tiny_downsampling_block_2', 'convnext_tiny_stage_2'],
        ['convnext_tiny_downsampling_block_3', 'convnext_tiny_stage_3'],
    ],
}


def get_backbone_blocks(backbone_name: str, base_model) -> list:
    """Return ordered list of layer groups [stem→output] for gradual unfreezing."""
    prefixes_list = _BACKBONE_BLOCKS.get(backbone_name, [])
    blocks = []
    for prefixes in prefixes_list:
        block = [l for l in base_model.layers if any(l.name.startswith(p) for p in prefixes)]
        if block:
            blocks.append(block)
    return blocks


_DOM_SHARED = [
    {'name': 'dropout_rate',  'type': 'continuous', 'domain': (0.1, 0.4)},
    {'name': 'l2_reg_log',   'type': 'continuous', 'domain': (-6.0, -1.0)},
    {'name': 'dense_units_1', 'type': 'discrete',   'domain': (0, 1, 2)},
    {'name': 'dense_units_2', 'type': 'discrete',   'domain': (0, 1, 2)},
]

STRATEGY_DOMAINS = {
    'FT':       _DOM_SHARED + [{'name': 'lr_log', 'type': 'continuous', 'domain': (-6.0, -2.0)}],
    'LP':       _DOM_SHARED + [{'name': 'lr_log', 'type': 'continuous', 'domain': (-6.0, -2.0)}],
    'G-LF':     _DOM_SHARED + [{'name': 'lr_log', 'type': 'continuous', 'domain': (-6.0, -2.0)}],
    'G-FL':     _DOM_SHARED + [{'name': 'lr_log', 'type': 'continuous', 'domain': (-6.0, -2.0)}],
    'Auto-RGN': _DOM_SHARED + [{'name': 'lr_log', 'type': 'continuous', 'domain': (-6.0, -2.0)}],
    'LP-FT':    _DOM_SHARED + [
        {'name': 'phase1_lr_log', 'type': 'continuous', 'domain': (-4.0, -2.0)},
        {'name': 'phase2_lr_log', 'type': 'continuous', 'domain': (-6.0, -4.0)},
    ],
    'L1-SP':    _DOM_SHARED + [
        {'name': 'lr_log',    'type': 'continuous', 'domain': (-6.0, -2.0)},
        {'name': 'alpha_log', 'type': 'continuous', 'domain': (-4.0, -1.0)},
        {'name': 'beta_log',  'type': 'continuous', 'domain': (-4.0, -1.0)},
    ],
    'L2-SP':    _DOM_SHARED + [
        {'name': 'lr_log',    'type': 'continuous', 'domain': (-6.0, -2.0)},
        {'name': 'alpha_log', 'type': 'continuous', 'domain': (-4.0, -1.0)},
        {'name': 'beta_log',  'type': 'continuous', 'domain': (-4.0, -1.0)},
    ],
}


def decode_strategy_params(x, strategy: str) -> dict:
    params = {
        'dropout_rate':  float(x[0]),
        'l2_reg':        float(10 ** x[1]),
        'dense_units_1': _DENSE1_CHOICES[int(round(x[2]))],
        'dense_units_2': _DENSE2_CHOICES[int(round(x[3]))],
        'batch_size':    CONFIG['batch_size_default'],
        'optimizer':     'adam',
    }
    if strategy in ('FT', 'LP', 'G-LF', 'G-FL', 'Auto-RGN'):
        params['lr'] = float(10 ** x[4])
    elif strategy == 'LP-FT':
        params['phase1_lr'] = float(10 ** x[4])
        params['phase2_lr'] = float(10 ** x[5])
    elif strategy in ('L1-SP', 'L2-SP'):
        params['lr']    = float(10 ** x[4])
        params['alpha'] = float(10 ** x[5])
        params['beta']  = float(10 ** x[6])
    return params


class StrategyTuner:
    """GPyOpt Bayesian tuner that is aware of the fine-tuning strategy."""
    def __init__(self, model_name, base_model_fn, strategy, backbone_name,
                 n_trials=10, log=print):
        self.model_name     = model_name
        self.base_model_fn  = base_model_fn
        self.strategy       = strategy
        self.backbone_name  = backbone_name
        self.n_trials       = n_trials
        self.log            = log
        self.best_params    = None
        self.best_value     = 0.0
        self._trial_num     = 0

    def _evaluate(self, X_gpyopt, X_full, y_full, fold_indices):
        x      = X_gpyopt[0]
        params = decode_strategy_params(x, self.strategy)
        self._trial_num += 1
        tid    = self._trial_num
        fold   = fold_indices[0]
        X_tr, y_tr = X_full[fold['train_idx']], y_full[fold['train_idx']]
        X_v,  y_v  = X_full[fold['val_idx']],   y_full[fold['val_idx']]
        try:
            base    = self.base_model_fn()
            trainer = DFUModelTrainer(
                model_name=f"{self.model_name}_trial{tid}_fold1",
                base_model=base,
                dropout_rate=params['dropout_rate'],
                l2_reg=params['l2_reg'],
                dense_units=(params['dense_units_1'], params['dense_units_2']),
                log=self.log,
                backbone_name=self.backbone_name,
            )
            trainer.build_model()
            trainer.train_with_strategy(
                self.strategy, X_tr, y_tr, X_v, y_v,
                params=params,
                max_epochs=CONFIG['max_epochs'],
                patience=CONFIG['phase1_patience'],
                verbose=0,
            )
            fold_auc = float(roc_auc_score(y_v, trainer.get_predictions(X_v)))
            del trainer, base
            tf.keras.backend.clear_session(); gc.collect()
            self.log(f"  Trial {tid}: fold1 AUC={fold_auc:.4f}  params={params}")
            return np.array([[-fold_auc]])
        except Exception as e:
            self.log(f"  Trial {tid} failed: {e}")
            try: del trainer
            except Exception: pass
            try: del base
            except Exception: pass
            tf.keras.backend.clear_session(); gc.collect()
            return np.array([[0.0]])

    def optimize(self, X_full, y_full, fold_indices):
        domain = STRATEGY_DOMAINS[self.strategy]
        self.log(f"\n{'='*80}\nStrategyTuner: {self.model_name}/{self.strategy} "
                 f"({self.n_trials} trials × fold1)\n{'='*80}")
        bo = GPyOpt.methods.BayesianOptimization(
            f=lambda x: self._evaluate(x, X_full, y_full, fold_indices),
            domain=domain,
            model_type='GP', acquisition_type='EI',
            exact_feval=False, maximize=False,
            verbosity=False, initial_design_numdata=1,
        )
        bo.run_optimization(max_iter=self.n_trials - 1)
        self.best_params = decode_strategy_params(bo.x_opt, self.strategy)
        self.best_value  = float(-bo.fx_opt)
        self.log(f"\n✓ Best fold1 AUC: {self.best_value:.6f}")
        self.log(f"Best params: {self.best_params}")
        tf.keras.backend.clear_session(); gc.collect()
        return self.best_params
