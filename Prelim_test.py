# ===== Markdown Cell 0 =====
# ## DFU Model Training - INAOE Dataset
# 
# This notebook implements model training using **preprocessed INAOE thermogram images**.
# 
# ### Dataset
# - **Source:** INAOE Plantar Thermogram Database (Preprocessed)
# - **Total Images:** 334 (244 DM + 90 CT)
# - **Status:** Ready to use (preprocessing already done)
# 
# ### Model Architecture
# - **EfficientNetB0**: Efficient mobile-friendly architecture
# - **ResNet50**: Deep residual learning baseline
# - **ConvNeXt-Tiny**: Modern convolutional neural network
# 
# ### Training Strategy
# - **Cross Validation:** 5-Fold stratified split
# - **Two-Phase Training:** Frozen backbone → Fine-tuning
# - **Hyperparameter Tuning:** Optuna (50 trials per model)
# - **Loss Function:** Binary cross-entropy with class weighting
# - **Threshold Optimization:** Sensitivity ≥ 85%
# 
# **Status:** Ready for training on INAOE preprocessed data

# ===== Markdown Cell 1 =====
# ## 1. Setup & Imports

# ===== Cell 2 =====
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
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image
import cv2
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    confusion_matrix, roc_curve, auc, roc_auc_score, classification_report
)
from sklearn.preprocessing import StandardScaler

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models
from tensorflow.keras.preprocessing.image import load_img, img_to_array
from tensorflow.keras.optimizers import Adam, RMSprop, SGD
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
from tensorflow.keras.applications import efficientnet, resnet50, convnext

import optuna
from optuna.trial import Trial
from optuna.samplers import TPESampler

# Suppress TensorFlow and absl warnings
warnings.filterwarnings('ignore')
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Suppress TF log levels
import logging
logging.getLogger('absl').setLevel(logging.ERROR)  # Suppress absl warnings

# Set random seeds for reproducibility
SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)

# Configure GPU memory growth
gpus = tf.config.list_physical_devices('GPU')
for gpu in gpus:
    tf.config.experimental.set_memory_growth(gpu, True)

# Configuration Parameters - USE INAOE PREPROCESSED DATASET
CONFIG = {
    'data_source': '/home/ntphoto/DFU/INAOE_Preprocessed',  # Use preprocessed dataset
    'checkpoint_dir': './model_checkpoints',
    'results_dir': './results',
    'img_size': (224, 224),
    'batch_size_default': 32,
    'max_epochs': 20,
    'phase1_patience': 5,
    'phase2_patience': 15,
    'n_folds': 5,
    'test_split': 0.2,
    'optuna_trials': 5,
    'phase2_lr_decay': 0.95,
    'phase2_decay_steps': 100,
}

# Create output directories
os.makedirs(CONFIG['checkpoint_dir'], exist_ok=True)
os.makedirs(CONFIG['results_dir'], exist_ok=True)

# Initialize logging
log_file = os.path.join(CONFIG['results_dir'], f"training_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

def log_message(message: str, print_also: bool = True):
    """Log message to file and optionally to console"""
    with open(log_file, 'a') as f:
        f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
    if print_also:
        print(message)

log_message("="*80)
log_message("DFU MODEL TRAINING - INAOE DATASET")
log_message(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
log_message(f"Data Source: {CONFIG['data_source']}")
log_message("="*80)

# ===== Markdown Cell 3 =====
# ## 2. Load Preprocessed INAOE Dataset

# ===== Cell 4 =====
# ============================================================
# LOAD PREPROCESSED INAOE DATASET
# ============================================================

def load_preprocessed_inaoe(data_dir: str) -> Tuple[np.ndarray, np.ndarray]:
    """
    Load preprocessed INAOE images from NPY files.
    
    Expected structure:
    - data_dir/
        - DM/       (label=1)
            - *.npy
        - CT/       (label=0)
            - *.npy
    
    Returns:
        images: (N, 224, 224, 3) normalized array [0, 1]
        labels: (N,) binary labels (0: CT, 1: DM)
    """
    images = []
    labels = []
    
    for group_idx, group in enumerate(['CT', 'DM']):
        group_dir = os.path.join(data_dir, group)
        
        if not os.path.exists(group_dir):
            raise FileNotFoundError(f"Group directory not found: {group_dir}")
        
        # Load all NPY files
        npy_files = sorted([f for f in os.listdir(group_dir) if f.endswith('.npy')])
        
        for npy_file in npy_files:
            npy_path = os.path.join(group_dir, npy_file)
            img_array = np.load(npy_path)
            
            images.append(img_array)
            labels.append(group_idx)  # 0: CT, 1: DM
    
    images = np.array(images, dtype=np.float32)
    labels = np.array(labels, dtype=np.int32)
    
    log_message(f"Loaded preprocessed INAOE dataset:")
    log_message(f"  - Total images: {len(images)}")
    log_message(f"  - Shape: {images.shape}")
    log_message(f"  - CT (label=0): {np.sum(labels == 0)}")
    log_message(f"  - DM (label=1): {np.sum(labels == 1)}")
    log_message(f"  - Value range: [{images.min():.4f}, {images.max():.4f}]")
    
    return images, labels

# Load data
log_message(f"\nLoading preprocessed images from: {CONFIG['data_source']}")
try:
    images, labels = load_preprocessed_inaoe(CONFIG['data_source'])
    log_message(f"✓ Data loading successful: {images.shape[0]} samples")
except Exception as e:
    log_message(f"✗ Error loading data: {str(e)}")
    raise

# Verify data integrity
assert images.shape[1:] == (224, 224, 3), "Image size mismatch"
assert np.min(images) >= 0 and np.max(images) <= 1, "Image normalization issue"
assert len(np.unique(labels)) == 2, "Expected binary classification"

log_message(f"\nData verification:")
log_message(f"  - Min/Max pixel values: {images.min():.4f} / {images.max():.4f}")
log_message(f"  - DM (1): {np.sum(labels == 1)} | CT (0): {np.sum(labels == 0)}")
log_message(f"  - Class balance: {np.sum(labels == 1) / len(labels) * 100:.2f}% DM")

# ===== Markdown Cell 5 =====
# ## 3. Train/Val/Test Split Logic

# ===== Cell 6 =====
def create_fold_splits(images: np.ndarray, labels: np.ndarray, n_splits: int = 5, 
                       test_split: float = 0.2, random_state: int = SEED):
    """
    Create 5-fold cross-validation splits with stratification.
    Each fold: 80% train/val, 20% held-out test.
    """
    # First split: (1 - test_split) for CV, test_split for final test set
    skf = StratifiedKFold(n_splits=max(2, int(round(1.0 / test_split))), shuffle=True, random_state=random_state)
    
    fold_indices = []
    test_indices = None
    
    # Get first split as test set
    for fold_idx, (train_val_idx, test_idx) in enumerate(skf.split(images, labels)):
        if fold_idx == 0:
            test_indices = test_idx
            break
    
    # Create 5 folds from remaining data (excluding test set)
    train_val_images = images[train_val_idx]
    train_val_labels = labels[train_val_idx]
    train_val_original_idx = train_val_idx
    
    # Create 5 folds with stratification
    skf_folds = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
    
    for fold_idx, (train_idx, val_idx) in enumerate(skf_folds.split(train_val_images, train_val_labels)):
        # Map back to original indices
        train_original = train_val_original_idx[train_idx]
        val_original = train_val_original_idx[val_idx]
        
        fold_indices.append({
            'fold': fold_idx,
            'train_idx': train_original,
            'val_idx': val_original
        })
    
    return fold_indices, test_indices

# Create folds
log_message("\nCreating 5-fold cross-validation splits...")
fold_indices, test_indices = create_fold_splits(
    images, labels,
    n_splits=CONFIG['n_folds'],
    test_split=CONFIG['test_split'],
    random_state=SEED
)

# Prepare test set
X_test = images[test_indices]
y_test = labels[test_indices]

log_message(f"✓ Created {len(fold_indices)} folds")
log_message(f"  - Test set size: {len(y_test)} (labels: {np.bincount(y_test)})")

for fold_info in fold_indices[:3]:  # Show first 3 folds
    fold_num = fold_info['fold']
    train_size = len(fold_info['train_idx'])
    val_size = len(fold_info['val_idx'])
    log_message(f"  - Fold {fold_num}: train={train_size}, val={val_size}")

# Alias (no copy — saves ~250MB RAM)
X_full = images
y_full = labels

log_message("✓ Data split creation complete")

# ===== Markdown Cell 7 =====
# ## 4. Custom Model Class with Two-Phase Training

# ===== Cell 8 =====
class ExponentialDecayScheduler(tf.keras.optimizers.schedules.LearningRateSchedule):
    """Custom learning rate schedule for Phase 2: lr_t = lr_0 * 0.95^(step/10000)"""
    
    def __init__(self, initial_lr: float, decay_rate: float = 0.95, decay_steps: int = 10000):
        self.initial_lr = initial_lr
        self.decay_rate = decay_rate
        self.decay_steps = decay_steps
    
    def __call__(self, step):
        return self.initial_lr * tf.pow(self.decay_rate, tf.cast(step, tf.float32) / self.decay_steps)
    
    def get_config(self):
        return {
            "initial_lr": self.initial_lr,
            "decay_rate": self.decay_rate,
            "decay_steps": self.decay_steps,
        }


class DFUModelTrainer:
    """Two-phase training strategy for transfer learning models"""
    
    def __init__(self, model_name: str, base_model, dropout_rate: float = 0.5, 
                 l2_reg: float = 1e-5, dense_units: Tuple[int, int] = (256, 64)):
        """
        Initialize model with custom head.
        
        Args:
            model_name: Name of the model architecture
            base_model: Pre-trained base model (without top layers)
            dropout_rate: Dropout rate for regularization
            l2_reg: L2 regularization coefficient
            dense_units: Tuple of (dense_layer1_units, dense_layer2_units)
        """
        self.model_name = model_name
        self.base_model = base_model
        self.dropout_rate = dropout_rate
        self.l2_reg = l2_reg
        self.dense_units = dense_units
        self.model = None
        self.history = None
        self.phase1_history = None
        self.phase2_history = None
    
    def build_model(self):
        """Build model with custom head"""
        # Freeze base model
        self.base_model.trainable = False
        
        # Build custom head
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
    
    def train_phase1(self, X_train, y_train, X_val, y_val, batch_size: int = 32,
                     optimizer: str = 'adam', learning_rate: float = 1e-3,
                     max_epochs: int = 100, patience: int = 5, verbose: int = 1):
        """
        Phase 1: Train custom head with frozen backbone
        
        Early stopping with patience=5 epochs
        """
        log_message(f"\n{'='*80}")
        log_message(f"PHASE 1: Training Custom Head (Frozen Backbone) - {self.model_name}")
        log_message(f"{'='*80}")
        
        # Compile with frozen backbone
        if optimizer.lower() == 'adam':
            opt = Adam(learning_rate=learning_rate)
        elif optimizer.lower() == 'rmsprop':
            opt = RMSprop(learning_rate=learning_rate)
        else:
            opt = SGD(learning_rate=learning_rate, momentum=0.9)
        
        self.model.compile(
            optimizer=opt,
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.AUC(name='auc')]
        )
        
        # Class weights for balanced training
        class_weights = {
            0: 1.0 / (np.sum(y_train == 0) / len(y_train)),
            1: 1.0 / (np.sum(y_train == 1) / len(y_train))
        }
        
        # Callbacks
        checkpoint_path = os.path.join(
            CONFIG['checkpoint_dir'],
            f"{self.model_name}_phase1_fold_best.h5"
        )
        
        callbacks = [
            EarlyStopping(
                monitor='val_loss',
                patience=patience,
                restore_best_weights=True,
                verbose=1
            ),
            ModelCheckpoint(
                checkpoint_path,
                monitor='val_loss',
                save_best_only=True,
                verbose=0
            )
        ]
        
        # Train Phase 1
        self.phase1_history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            batch_size=batch_size,
            epochs=max_epochs,
            class_weight=class_weights,
            callbacks=callbacks,
            verbose=verbose
        )
        
        log_message(f"Phase 1 training complete. Best val_loss: {min(self.phase1_history.history['val_loss']):.6f}")
    
    def train_phase2(self, X_train, y_train, X_val, y_val, batch_size: int = 32,
                     optimizer: str = 'adam', learning_rate: float = 1e-4,
                     max_epochs: int = 100, patience: int = 15, verbose: int = 1):
        """
        Phase 2: Fine-tune with unfrozen top layers using exponential decay
        
        Learning rate schedule: lr_t = lr_0 × 0.95^(t/10000)
        Early stopping with patience=15 epochs (continuing from Phase 1)
        """
        log_message(f"\n{'='*80}")
        log_message(f"PHASE 2: Fine-tuning with Top Layers Unfrozen - {self.model_name}")
        log_message(f"{'='*80}")
        
        # Unfreeze top layers of backbone
        num_layers = len(self.base_model.layers)
        unfreeze_from = int(num_layers * 0.7)  # Unfreeze top 30% of layers
        
        for layer in self.base_model.layers[unfreeze_from:]:
            layer.trainable = True
        
        log_message(f"Unfroze {num_layers - unfreeze_from} layers (from layer {unfreeze_from})")
        
        # Compile with exponential decay
        lr_schedule = ExponentialDecayScheduler(
            initial_lr=learning_rate,
            decay_rate=CONFIG['phase2_lr_decay'],
            decay_steps=CONFIG['phase2_decay_steps']
        )
        
        if optimizer.lower() == 'adam':
            opt = Adam(learning_rate=lr_schedule)
        elif optimizer.lower() == 'rmsprop':
            opt = RMSprop(learning_rate=lr_schedule)
        else:
            opt = SGD(learning_rate=lr_schedule, momentum=0.9)
        
        self.model.compile(
            optimizer=opt,
            loss='binary_crossentropy',
            metrics=['accuracy', tf.keras.metrics.AUC(name='auc')]
        )
        
        # Class weights
        class_weights = {
            0: 1.0 / (np.sum(y_train == 0) / len(y_train)),
            1: 1.0 / (np.sum(y_train == 1) / len(y_train))
        }
        
        # Callbacks
        checkpoint_path = os.path.join(
            CONFIG['checkpoint_dir'],
            f"{self.model_name}_phase2_fold_best.h5"
        )
        
        callbacks = [
            EarlyStopping(
                monitor='val_loss',
                patience=patience,
                restore_best_weights=True,
                verbose=1
            ),
            ModelCheckpoint(
                checkpoint_path,
                monitor='val_loss',
                save_best_only=True,
                verbose=0
            )
        ]
        
        # Train Phase 2
        self.phase2_history = self.model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            batch_size=batch_size,
            epochs=max_epochs,
            class_weight=class_weights,
            callbacks=callbacks,
            verbose=verbose
        )
        
        log_message(f"Phase 2 training complete. Best val_loss: {min(self.phase2_history.history['val_loss']):.6f}")
        log_message(f"{'='*80}\n")
    
    def get_predictions(self, X):
        """Get model predictions"""
        return self.model.predict(X, verbose=0).flatten()
    
    def save_model(self, path: str):
        """Save model to disk in Keras 3 format"""
        # Change .h5 to .keras for native Keras format
        if path.endswith('.h5'):
            path = path.replace('.h5', '.keras')
        self.model.save(path)
        log_message(f"Model saved to {path}")

# ===== Markdown Cell 9 =====
# ## 5. Hyperparameter Tuning with Optuna

# ===== Cell 10 =====
class OptunaHyperparameterTuner:
    """Optuna-based hyperparameter optimization for DFU models (5-fold CV)."""

    def __init__(self, model_name: str, base_model_fn, n_trials: int = 50):
        self.model_name = model_name
        self.base_model_fn = base_model_fn
        self.n_trials = n_trials
        self.best_params = None
        self.best_value = 0
        self.study = None

    def objective(self, trial: optuna.Trial, X_full: np.ndarray, y_full: np.ndarray, fold_indices: list) -> float:
        # ── Sample hyperparameters ──────────────────────────────
        params = {
            'dropout_rate':   trial.suggest_float('dropout_rate', 0.2, 0.5),
            'l2_reg':         trial.suggest_float('l2_reg', 1e-5, 1e-2, log=True),
            'dense_units_1':  trial.suggest_categorical('dense_units_1', [128, 256, 512]),
            'dense_units_2':  trial.suggest_categorical('dense_units_2', [64, 128, 256]),
            'batch_size':     trial.suggest_categorical('batch_size', [16, 32]),
            'optimizer':      trial.suggest_categorical('optimizer', ['adam']),
            'phase1_lr':      trial.suggest_float('phase1_lr', 1e-4, 1e-2, log=True),
            'phase2_lr':      trial.suggest_float('phase2_lr', 1e-6, 1e-4, log=True),
        }

        try:
            fold_aucs = []

            # ── 5-fold CV ───────────────────────────────────────
            for fold_idx, fold_info in enumerate(fold_indices):
                X_train = X_full[fold_info['train_idx']]
                y_train = y_full[fold_info['train_idx']]
                X_val   = X_full[fold_info['val_idx']]
                y_val   = y_full[fold_info['val_idx']]

                base_model = self.base_model_fn()
                trainer = DFUModelTrainer(
                    model_name=f"{self.model_name}_trial{trial.number}_fold{fold_idx+1}",
                    base_model=base_model,
                    dropout_rate=params['dropout_rate'],
                    l2_reg=params['l2_reg'],
                    dense_units=(params['dense_units_1'], params['dense_units_2'])
                )
                trainer.build_model()

                trainer.train_phase1(
                    X_train, y_train, X_val, y_val,
                    batch_size=params['batch_size'],
                    optimizer=params['optimizer'],
                    learning_rate=params['phase1_lr'],
                    max_epochs=CONFIG['max_epochs'],
                    patience=CONFIG['phase1_patience'],
                    verbose=0
                )
                trainer.train_phase2(
                    X_train, y_train, X_val, y_val,
                    batch_size=params['batch_size'],
                    optimizer=params['optimizer'],
                    learning_rate=params['phase2_lr'],
                    max_epochs=CONFIG['max_epochs'],
                    patience=CONFIG['phase2_patience'],
                    verbose=0
                )

                val_preds = trainer.get_predictions(X_val)
                fold_aucs.append(float(roc_auc_score(y_val, val_preds)))

                # Free GPU memory before next fold (prevent VRAM leak across folds/trials)
                del trainer, base_model
                tf.keras.backend.clear_session()
                gc.collect()

            mean_auc = float(np.mean(fold_aucs))
            log_message(f"  Trial {trial.number}: mean AUC = {mean_auc:.4f}  (folds: {[f'{a:.4f}' for a in fold_aucs]})")
            return mean_auc

        except Exception as e:
            log_message(f"Trial {trial.number} failed: {str(e)}")
            return 0.0

    def optimize(self, X_full: np.ndarray, y_full: np.ndarray, fold_indices: list):
        """Run Optuna optimization with 5-fold CV."""
        log_message(f"\n{'='*80}")
        log_message(f"OPTUNA HYPERPARAMETER TUNING: {self.model_name}")
        log_message(f"Number of trials: {self.n_trials}  |  Folds per trial: {len(fold_indices)}")
        log_message(f"{'='*80}")

        sampler = TPESampler(seed=SEED)
        self.study = optuna.create_study(direction='maximize', sampler=sampler)

        self.study.optimize(
            lambda trial: self.objective(trial, X_full, y_full, fold_indices),
            n_trials=self.n_trials,
            show_progress_bar=True
        )

        self.best_params = self.study.best_params
        self.best_value = self.study.best_value

        log_message(f"\n✓ Optimization complete")
        log_message(f"Best mean CV AUC: {self.best_value:.6f}")
        log_message(f"Best hyperparameters:")
        for key, value in self.best_params.items():
            log_message(f"  - {key}: {value}")

        return self.best_params


def create_base_models():
    """Create base models with ImageNet weights"""
    def efficientnet_b0():
        return efficientnet.EfficientNetB0(
            weights='imagenet',
            include_top=False,
            input_shape=(224, 224, 3)
        )
    
    def create_resnet50():
        return resnet50.ResNet50(
            weights='imagenet',
            include_top=False,
            input_shape=(224, 224, 3)
        )
    
    def convnext_tiny():
        return convnext.ConvNeXtTiny(
            weights='imagenet',
            include_top=False,
            input_shape=(224, 224, 3)
        )
    
    return {
        'EfficientNetB0': efficientnet_b0,
        'ResNet50': create_resnet50,
        'ConvNeXt-Tiny': convnext_tiny
    }

base_model_creators = create_base_models()

log_message("✓ Optuna tuner and base model creators initialized")

# ===== Markdown Cell 11 =====
# ## 6. Train EfficientNetB0 Model

# ===== Cell 12 =====
# ============================================================
# Training EfficientNetB0
# Resume-aware: skips Optuna if best_params exists,
# skips individual folds if their checkpoint exists.
# ============================================================

model_name_efficientnet = 'EfficientNetB0'
efficientnet_results = {
    'fold_models': [],
    'fold_histories': [],
    'fold_val_predictions': [],
    'fold_best_thresholds': [],
    'fold_metrics': []
}

log_message(f"\n{'#'*80}")
log_message(f"# TRAINING {model_name_efficientnet}")
log_message(f"{'#'*80}\n")

checkpoint_paths_eff = [
    os.path.join(CONFIG['checkpoint_dir'], f"{model_name_efficientnet}_Fold{i+1}_final.keras")
    for i in range(CONFIG['n_folds'])
]
best_params_path_eff = os.path.join(CONFIG['checkpoint_dir'], f"{model_name_efficientnet}_best_params.json")

# ── STEP 1: Hyperparameters (skip if already saved) ───────
if os.path.exists(best_params_path_eff):
    with open(best_params_path_eff, 'r') as _f:
        best_params = json.load(_f)
    log_message(f"✓ Loaded existing best_params from {best_params_path_eff} — skipping Optuna\n")
else:
    log_message(f"--- STEP 1: Hyperparameter Tuning (5-FOLD CV) ---")
    tuner = OptunaHyperparameterTuner(
        model_name=f"{model_name_efficientnet}_HyperparameterSearch",
        base_model_fn=base_model_creators['EfficientNetB0'],
        n_trials=CONFIG['optuna_trials']
    )
    best_params = tuner.optimize(X_full, y_full, fold_indices)

    with open(best_params_path_eff, 'w') as _f:
        json.dump(best_params, _f, indent=2)
    log_message(f"✓ best_params saved to {best_params_path_eff}\n")

# ── STEP 2: Per-fold training (resume from existing checkpoints) ───
log_message(f"--- STEP 2: Per-Fold Training (ALL {CONFIG['n_folds']} FOLDS) ---\n")

for fold_num, fold_info in enumerate(fold_indices):
    ckpt_path = checkpoint_paths_eff[fold_num]
    val_idx   = fold_info['val_idx']
    X_val_fold = X_full[val_idx]
    y_val_fold = y_full[val_idx]

    if os.path.exists(ckpt_path):
        log_message(f"✓ Fold {fold_num+1}: checkpoint found — loading from {ckpt_path}")
        model = tf.keras.models.load_model(ckpt_path)
        val_predictions = model.predict(X_val_fold, verbose=0).flatten()
        efficientnet_results['fold_models'].append(ckpt_path)  # store path, not model
        efficientnet_results['fold_histories'].append({'phase1': {}, 'phase2': {}})
        efficientnet_results['fold_val_predictions'].append(val_predictions)
        del model
        tf.keras.backend.clear_session(); gc.collect()
        continue

    log_message(f"\n{'='*80}")
    log_message(f"FOLD {fold_num+1}/{len(fold_indices)}: {model_name_efficientnet}  [TRAINING]")
    log_message(f"{'='*80}")

    train_idx    = fold_info['train_idx']
    X_train_fold = X_full[train_idx]
    y_train_fold = y_full[train_idx]

    log_message(f"Train: {len(X_train_fold)} | Val: {len(X_val_fold)}")

    base_model = base_model_creators['EfficientNetB0']()
    trainer = DFUModelTrainer(
        model_name=f"{model_name_efficientnet}_Fold{fold_num+1}",
        base_model=base_model,
        dropout_rate=best_params['dropout_rate'],
        l2_reg=best_params['l2_reg'],
        dense_units=(best_params['dense_units_1'], best_params['dense_units_2'])
    )
    trainer.build_model()

    trainer.train_phase1(
        X_train_fold, y_train_fold, X_val_fold, y_val_fold,
        batch_size=best_params['batch_size'],
        optimizer=best_params['optimizer'],
        learning_rate=best_params['phase1_lr'],
        max_epochs=CONFIG['max_epochs'],
        patience=CONFIG['phase1_patience'],
        verbose=1
    )
    trainer.train_phase2(
        X_train_fold, y_train_fold, X_val_fold, y_val_fold,
        batch_size=best_params['batch_size'],
        optimizer=best_params['optimizer'],
        learning_rate=best_params['phase2_lr'],
        max_epochs=CONFIG['max_epochs'],
        patience=CONFIG['phase2_patience'],
        verbose=1
    )

    val_predictions = trainer.get_predictions(X_val_fold)
    trainer.save_model(ckpt_path)
    efficientnet_results['fold_models'].append(ckpt_path)  # path instead of model
    efficientnet_results['fold_histories'].append({
        'phase1': trainer.phase1_history.history,
        'phase2': trainer.phase2_history.history
    })
    efficientnet_results['fold_val_predictions'].append(val_predictions)
    log_message(f"✓ Fold {fold_num+1} training complete — saved to {ckpt_path}")

    del trainer, base_model
    tf.keras.backend.clear_session(); gc.collect()

# ── Post-Training Metrics Summary ─────────────────────────
log_message(f"\n────────────────────────────────────────────────────────────")
log_message(f"  {model_name_efficientnet} — Validation Metrics Per Fold")
log_message(f"────────────────────────────────────────────────────────────")
_fold_aucs, _fold_sens, _fold_spec = [], [], []
for _fn, (_fi, _vp) in enumerate(zip(fold_indices, efficientnet_results['fold_val_predictions'])):
    _y_val = y_full[_fi['val_idx']]
    _auc  = roc_auc_score(_y_val, _vp)
    _yb   = (_vp >= 0.5).astype(int)
    _tp   = int(np.sum((_yb == 1) & (_y_val == 1)))
    _fp   = int(np.sum((_yb == 1) & (_y_val == 0)))
    _fn2  = int(np.sum((_yb == 0) & (_y_val == 1)))
    _tn   = int(np.sum((_yb == 0) & (_y_val == 0)))
    _sens = _tp / (_tp + _fn2) if (_tp + _fn2) > 0 else 0.0
    _spec = _tn / (_tn + _fp)  if (_tn + _fp)  > 0 else 0.0
    _fold_aucs.append(_auc); _fold_sens.append(_sens); _fold_spec.append(_spec)
    log_message(f"  Fold {_fn+1}:  AUC-ROC={_auc:.4f}  Sensitivity={_sens:.4f}  Specificity={_spec:.4f}")
log_message(f"────────────────────────────────────────────────────────────")
log_message(f"  Mean :  AUC-ROC={np.mean(_fold_aucs):.4f}  Sensitivity={np.mean(_fold_sens):.4f}  Specificity={np.mean(_fold_spec):.4f}")
log_message(f"  Std  :  AUC-ROC={np.std(_fold_aucs):.4f}   Sensitivity={np.std(_fold_sens):.4f}   Specificity={np.std(_fold_spec):.4f}")
log_message(f"────────────────────────────────────────────────────────────\n")

log_message(f"\n{'#'*80}")
log_message(f"# {model_name_efficientnet} TRAINING COMPLETE")
log_message(f"{'#'*80}\n")

# ===== Markdown Cell 13 =====
# ## 7. Train ResNet50 Model

# ===== Cell 14 =====
# ============================================================
# Training ResNet50
# Resume-aware: skips Optuna if best_params exists,
# skips individual folds if their checkpoint exists.
# ============================================================

model_name_resnet = 'ResNet50'
resnet_results = {
    'fold_models': [],
    'fold_histories': [],
    'fold_val_predictions': [],
    'fold_best_thresholds': [],
    'fold_metrics': []
}

log_message(f"\n{'#'*80}")
log_message(f"# TRAINING {model_name_resnet}")
log_message(f"{'#'*80}\n")

checkpoint_paths_res = [
    os.path.join(CONFIG['checkpoint_dir'], f"{model_name_resnet}_Fold{i+1}_final.keras")
    for i in range(CONFIG['n_folds'])
]
best_params_path_res = os.path.join(CONFIG['checkpoint_dir'], f"{model_name_resnet}_best_params.json")

# ── STEP 1: Hyperparameters (skip if already saved) ───────
if os.path.exists(best_params_path_res):
    with open(best_params_path_res, 'r') as _f:
        best_params = json.load(_f)
    log_message(f"✓ Loaded existing best_params from {best_params_path_res} — skipping Optuna\n")
else:
    log_message(f"--- STEP 1: Hyperparameter Tuning (5-FOLD CV) ---")
    tuner = OptunaHyperparameterTuner(
        model_name=f"{model_name_resnet}_HyperparameterSearch",
        base_model_fn=base_model_creators['ResNet50'],
        n_trials=CONFIG['optuna_trials']
    )
    best_params = tuner.optimize(X_full, y_full, fold_indices)

    with open(best_params_path_res, 'w') as _f:
        json.dump(best_params, _f, indent=2)
    log_message(f"✓ best_params saved to {best_params_path_res}\n")

# ── STEP 2: Per-fold training (resume from existing checkpoints) ───
log_message(f"--- STEP 2: Per-Fold Training (ALL {CONFIG['n_folds']} FOLDS) ---\n")

for fold_num, fold_info in enumerate(fold_indices):
    ckpt_path  = checkpoint_paths_res[fold_num]
    val_idx    = fold_info['val_idx']
    X_val_fold = X_full[val_idx]
    y_val_fold = y_full[val_idx]

    if os.path.exists(ckpt_path):
        log_message(f"✓ Fold {fold_num+1}: checkpoint found — loading from {ckpt_path}")
        model = tf.keras.models.load_model(ckpt_path)
        val_predictions = model.predict(X_val_fold, verbose=0).flatten()
        resnet_results['fold_models'].append(ckpt_path)
        resnet_results['fold_histories'].append({'phase1': {}, 'phase2': {}})
        resnet_results['fold_val_predictions'].append(val_predictions)
        del model
        tf.keras.backend.clear_session(); gc.collect()
        continue

    log_message(f"\n{'='*80}")
    log_message(f"FOLD {fold_num+1}/{len(fold_indices)}: {model_name_resnet}  [TRAINING]")
    log_message(f"{'='*80}")

    train_idx    = fold_info['train_idx']
    X_train_fold = X_full[train_idx]
    y_train_fold = y_full[train_idx]

    log_message(f"Train: {len(X_train_fold)} | Val: {len(X_val_fold)}")

    base_model = base_model_creators['ResNet50']()
    trainer = DFUModelTrainer(
        model_name=f"{model_name_resnet}_Fold{fold_num+1}",
        base_model=base_model,
        dropout_rate=best_params['dropout_rate'],
        l2_reg=best_params['l2_reg'],
        dense_units=(best_params['dense_units_1'], best_params['dense_units_2'])
    )
    trainer.build_model()

    trainer.train_phase1(
        X_train_fold, y_train_fold, X_val_fold, y_val_fold,
        batch_size=best_params['batch_size'],
        optimizer=best_params['optimizer'],
        learning_rate=best_params['phase1_lr'],
        max_epochs=CONFIG['max_epochs'],
        patience=CONFIG['phase1_patience'],
        verbose=1
    )
    trainer.train_phase2(
        X_train_fold, y_train_fold, X_val_fold, y_val_fold,
        batch_size=best_params['batch_size'],
        optimizer=best_params['optimizer'],
        learning_rate=best_params['phase2_lr'],
        max_epochs=CONFIG['max_epochs'],
        patience=CONFIG['phase2_patience'],
        verbose=1
    )

    val_predictions = trainer.get_predictions(X_val_fold)
    trainer.save_model(ckpt_path)
    resnet_results['fold_models'].append(ckpt_path)
    resnet_results['fold_histories'].append({
        'phase1': trainer.phase1_history.history,
        'phase2': trainer.phase2_history.history
    })
    resnet_results['fold_val_predictions'].append(val_predictions)
    log_message(f"✓ Fold {fold_num+1} training complete — saved to {ckpt_path}")

    del trainer, base_model
    tf.keras.backend.clear_session(); gc.collect()

# ── Post-Training Metrics Summary ─────────────────────────
log_message(f"\n────────────────────────────────────────────────────────────")
log_message(f"  {model_name_resnet} — Validation Metrics Per Fold")
log_message(f"────────────────────────────────────────────────────────────")
_fold_aucs, _fold_sens, _fold_spec = [], [], []
for _fn, (_fi, _vp) in enumerate(zip(fold_indices, resnet_results['fold_val_predictions'])):
    _y_val = y_full[_fi['val_idx']]
    _auc  = roc_auc_score(_y_val, _vp)
    _yb   = (_vp >= 0.5).astype(int)
    _tp   = int(np.sum((_yb == 1) & (_y_val == 1)))
    _fp   = int(np.sum((_yb == 1) & (_y_val == 0)))
    _fn2  = int(np.sum((_yb == 0) & (_y_val == 1)))
    _tn   = int(np.sum((_yb == 0) & (_y_val == 0)))
    _sens = _tp / (_tp + _fn2) if (_tp + _fn2) > 0 else 0.0
    _spec = _tn / (_tn + _fp)  if (_tn + _fp)  > 0 else 0.0
    _fold_aucs.append(_auc); _fold_sens.append(_sens); _fold_spec.append(_spec)
    log_message(f"  Fold {_fn+1}:  AUC-ROC={_auc:.4f}  Sensitivity={_sens:.4f}  Specificity={_spec:.4f}")
log_message(f"────────────────────────────────────────────────────────────")
log_message(f"  Mean :  AUC-ROC={np.mean(_fold_aucs):.4f}  Sensitivity={np.mean(_fold_sens):.4f}  Specificity={np.mean(_fold_spec):.4f}")
log_message(f"  Std  :  AUC-ROC={np.std(_fold_aucs):.4f}   Sensitivity={np.std(_fold_sens):.4f}   Specificity={np.std(_fold_spec):.4f}")
log_message(f"────────────────────────────────────────────────────────────\n")

log_message(f"\n{'#'*80}")
log_message(f"# {model_name_resnet} TRAINING COMPLETE")
log_message(f"{'#'*80}\n")

# ===== Markdown Cell 15 =====
# ## 8. Train ConvNeXt-Tiny Model

# ===== Cell 16 =====
# ============================================================
# Training ConvNeXt-Tiny
# Resume-aware: skips Optuna if best_params exists,
# skips individual folds if their checkpoint exists.
# ============================================================

model_name_convnext = 'ConvNeXt-Tiny'
convnext_results = {
    'fold_models': [],
    'fold_histories': [],
    'fold_val_predictions': [],
    'fold_best_thresholds': [],
    'fold_metrics': []
}

log_message(f"\n{'#'*80}")
log_message(f"# TRAINING {model_name_convnext}")
log_message(f"{'#'*80}\n")

checkpoint_paths_cnx = [
    os.path.join(CONFIG['checkpoint_dir'], f"{model_name_convnext}_Fold{i+1}_final.keras")
    for i in range(CONFIG['n_folds'])
]
best_params_path_cnx = os.path.join(CONFIG['checkpoint_dir'], f"{model_name_convnext}_best_params.json")

# ── STEP 1: Hyperparameters (skip if already saved) ───────
if os.path.exists(best_params_path_cnx):
    with open(best_params_path_cnx, 'r') as _f:
        best_params = json.load(_f)
    log_message(f"✓ Loaded existing best_params from {best_params_path_cnx} — skipping Optuna\n")
else:
    log_message(f"--- STEP 1: Hyperparameter Tuning (5-FOLD CV) ---")
    tuner = OptunaHyperparameterTuner(
        model_name=f"{model_name_convnext}_HyperparameterSearch",
        base_model_fn=base_model_creators['ConvNeXt-Tiny'],
        n_trials=CONFIG['optuna_trials']
    )
    best_params = tuner.optimize(X_full, y_full, fold_indices)

    with open(best_params_path_cnx, 'w') as _f:
        json.dump(best_params, _f, indent=2)
    log_message(f"✓ best_params saved to {best_params_path_cnx}\n")

# ── STEP 2: Per-fold training (resume from existing checkpoints) ───
log_message(f"--- STEP 2: Per-Fold Training (ALL {CONFIG['n_folds']} FOLDS) ---\n")

for fold_num, fold_info in enumerate(fold_indices):
    ckpt_path  = checkpoint_paths_cnx[fold_num]
    val_idx    = fold_info['val_idx']
    X_val_fold = X_full[val_idx]
    y_val_fold = y_full[val_idx]

    if os.path.exists(ckpt_path):
        log_message(f"✓ Fold {fold_num+1}: checkpoint found — loading from {ckpt_path}")
        model = tf.keras.models.load_model(ckpt_path)
        val_predictions = model.predict(X_val_fold, verbose=0).flatten()
        convnext_results['fold_models'].append(ckpt_path)
        convnext_results['fold_histories'].append({'phase1': {}, 'phase2': {}})
        convnext_results['fold_val_predictions'].append(val_predictions)
        del model
        tf.keras.backend.clear_session(); gc.collect()
        continue

    log_message(f"\n{'='*80}")
    log_message(f"FOLD {fold_num+1}/{len(fold_indices)}: {model_name_convnext}  [TRAINING]")
    log_message(f"{'='*80}")

    train_idx    = fold_info['train_idx']
    X_train_fold = X_full[train_idx]
    y_train_fold = y_full[train_idx]

    log_message(f"Train: {len(X_train_fold)} | Val: {len(X_val_fold)}")

    base_model = base_model_creators['ConvNeXt-Tiny']()
    trainer = DFUModelTrainer(
        model_name=f"{model_name_convnext}_Fold{fold_num+1}",
        base_model=base_model,
        dropout_rate=best_params['dropout_rate'],
        l2_reg=best_params['l2_reg'],
        dense_units=(best_params['dense_units_1'], best_params['dense_units_2'])
    )
    trainer.build_model()

    trainer.train_phase1(
        X_train_fold, y_train_fold, X_val_fold, y_val_fold,
        batch_size=best_params['batch_size'],
        optimizer=best_params['optimizer'],
        learning_rate=best_params['phase1_lr'],
        max_epochs=CONFIG['max_epochs'],
        patience=CONFIG['phase1_patience'],
        verbose=1
    )
    trainer.train_phase2(
        X_train_fold, y_train_fold, X_val_fold, y_val_fold,
        batch_size=best_params['batch_size'],
        optimizer=best_params['optimizer'],
        learning_rate=best_params['phase2_lr'],
        max_epochs=CONFIG['max_epochs'],
        patience=CONFIG['phase2_patience'],
        verbose=1
    )

    val_predictions = trainer.get_predictions(X_val_fold)
    trainer.save_model(ckpt_path)
    convnext_results['fold_models'].append(ckpt_path)
    convnext_results['fold_histories'].append({
        'phase1': trainer.phase1_history.history,
        'phase2': trainer.phase2_history.history
    })
    convnext_results['fold_val_predictions'].append(val_predictions)
    log_message(f"✓ Fold {fold_num+1} training complete — saved to {ckpt_path}")

    del trainer, base_model
    tf.keras.backend.clear_session(); gc.collect()

# ── Post-Training Metrics Summary ─────────────────────────
log_message(f"\n────────────────────────────────────────────────────────────")
log_message(f"  {model_name_convnext} — Validation Metrics Per Fold")
log_message(f"────────────────────────────────────────────────────────────")
_fold_aucs, _fold_sens, _fold_spec = [], [], []
for _fn, (_fi, _vp) in enumerate(zip(fold_indices, convnext_results['fold_val_predictions'])):
    _y_val = y_full[_fi['val_idx']]
    _auc  = roc_auc_score(_y_val, _vp)
    _yb   = (_vp >= 0.5).astype(int)
    _tp   = int(np.sum((_yb == 1) & (_y_val == 1)))
    _fp   = int(np.sum((_yb == 1) & (_y_val == 0)))
    _fn2  = int(np.sum((_yb == 0) & (_y_val == 1)))
    _tn   = int(np.sum((_yb == 0) & (_y_val == 0)))
    _sens = _tp / (_tp + _fn2) if (_tp + _fn2) > 0 else 0.0
    _spec = _tn / (_tn + _fp)  if (_tn + _fp)  > 0 else 0.0
    _fold_aucs.append(_auc); _fold_sens.append(_sens); _fold_spec.append(_spec)
    log_message(f"  Fold {_fn+1}:  AUC-ROC={_auc:.4f}  Sensitivity={_sens:.4f}  Specificity={_spec:.4f}")
log_message(f"────────────────────────────────────────────────────────────")
log_message(f"  Mean :  AUC-ROC={np.mean(_fold_aucs):.4f}  Sensitivity={np.mean(_fold_sens):.4f}  Specificity={np.mean(_fold_spec):.4f}")
log_message(f"  Std  :  AUC-ROC={np.std(_fold_aucs):.4f}   Sensitivity={np.std(_fold_sens):.4f}   Specificity={np.std(_fold_spec):.4f}")
log_message(f"────────────────────────────────────────────────────────────\n")

log_message(f"\n{'#'*80}")
log_message(f"# {model_name_convnext} TRAINING COMPLETE")
log_message(f"{'#'*80}\n")

# ===== Markdown Cell 17 =====
# ## 9. Comparison Result

# ===== Cell 18 =====
log_message("="*80)
log_message("5-FOLD CV MEAN RESULTS COMPARISON")
log_message("="*80 + "\n")

criteria = {
    'auc_threshold': 0.8,
    'sensitivity_threshold': 0.85,
    'specificity_threshold': 0.7
}

log_message("Criteria:")
log_message(f"  - Mean AUC-ROC > {criteria['auc_threshold']}")
log_message(f"  - Mean Sensitivity > {criteria['sensitivity_threshold']}")
log_message(f"  - Mean Specificity > {criteria['specificity_threshold']}\n")

models_to_check = [
    (model_name_efficientnet, efficientnet_results),
    (model_name_resnet, resnet_results),
    (model_name_convnext, convnext_results)
]

def _compute_mean_cv_metrics(results, fold_indices, y_full):
    aucs, sens, specs = [], [], []
    for fi, vp in zip(fold_indices, results['fold_val_predictions']):
        y_val = y_full[fi['val_idx']]
        aucs.append(roc_auc_score(y_val, vp))
        yb = (vp >= 0.5).astype(int)
        tp = int(np.sum((yb == 1) & (y_val == 1)))
        fn = int(np.sum((yb == 0) & (y_val == 1)))
        tn = int(np.sum((yb == 0) & (y_val == 0)))
        fp = int(np.sum((yb == 1) & (y_val == 0)))
        sens.append(tp / (tp + fn) if (tp + fn) > 0 else 0.0)
        specs.append(tn / (tn + fp) if (tn + fp) > 0 else 0.0)
    return float(np.mean(aucs)), float(np.mean(sens)), float(np.mean(specs))

model_summary = []
for name, results in models_to_check:
    mean_auc, mean_sens, mean_spec = _compute_mean_cv_metrics(results, fold_indices, y_full)
    pass_auc = mean_auc > criteria['auc_threshold']
    pass_sens = mean_sens > criteria['sensitivity_threshold']
    pass_spec = mean_spec > criteria['specificity_threshold']
    qualifies = pass_auc and pass_sens and pass_spec

    log_message(f"{name} (5-Fold Mean):")
    log_message(f"  • Mean AUC-ROC:     {mean_auc:.4f} {'✓ PASS' if pass_auc else '✗ FAIL'}")
    log_message(f"  • Mean Sensitivity: {mean_sens:.4f} {'✓ PASS' if pass_sens else '✗ FAIL'}")
    log_message(f"  • Mean Specificity: {mean_spec:.4f} {'✓ PASS' if pass_spec else '✗ FAIL'}")
    log_message(f"  -> MEETS ALL CRITERIA: {'YES ✓' if qualifies else 'NO ✗'}\n")

    model_summary.append({
        'name': name, 'results': results,
        'auc': mean_auc, 'sens': mean_sens, 'spec': mean_spec,
        'qualifies': qualifies
    })

# ── Select best model ─────────────────────────────────────
qualified = [m for m in model_summary if m['qualifies']]
if qualified:
    best = max(qualified, key=lambda m: m['auc'])
    log_message(f"✓ {len(qualified)} model(s) passed all criteria. Selecting highest AUC-ROC.")
else:
    best = max(model_summary, key=lambda m: m['auc'])
    log_message(f"⚠ No model passed all criteria. Falling back to highest AUC-ROC.")

best_model_name_for_deployment = best['name']
best_model_results = best['results']
log_message(f"→ BEST MODEL: {best_model_name_for_deployment}  (AUC={best['auc']:.4f}, Sens={best['sens']:.4f}, Spec={best['spec']:.4f})\n")


# ===== Markdown Cell 19 =====
# ## 10. Threshold Optimization

# ===== Cell 20 =====
def optimize_threshold_per_fold(y_true, y_pred, target_sensitivity=0.85):
    """
    Optimize classification threshold to achieve target sensitivity.
    """
    fpr, tpr, thresholds = roc_curve(y_true, y_pred)
    
    # Find threshold with sensitivity >= target_sensitivity
    valid_thresholds = []
    for i, threshold in enumerate(thresholds):
        sensitivity = tpr[i]
        if sensitivity >= target_sensitivity:
            specificity = 1 - fpr[i]
            valid_thresholds.append({
                'threshold': threshold,
                'sensitivity': sensitivity,
                'specificity': specificity,
                'distance': abs(sensitivity - 1) + abs(specificity - 1)
            })
    
    if not valid_thresholds:
        best_idx = np.argmax(tpr)
        optimal_threshold = thresholds[best_idx]
    else:
        optimal_threshold = max(valid_thresholds, key=lambda x: x['specificity'])['threshold']
    
    return optimal_threshold, fpr, tpr, thresholds

log_message(f"\n{'='*80}")
log_message(f"THRESHOLD OPTIMIZATION (BEST MODEL: {best_model_name_for_deployment})")
log_message(f"{'='*80}\n")

best_model_results['fold_best_thresholds'] = []
for fold_num, (fold_info, val_preds) in enumerate(zip(fold_indices, best_model_results['fold_val_predictions'])):
    val_idx = fold_info['val_idx']
    y_val = y_full[val_idx]

    threshold, fpr, tpr, thresholds = optimize_threshold_per_fold(y_val, val_preds)
    best_model_results['fold_best_thresholds'].append(threshold)

    y_pred_binary = (val_preds >= threshold).astype(int)
    sensitivity = recall_score(y_val, y_pred_binary, zero_division=0)
    specificity = 1 - fpr[np.argmin(np.abs(thresholds - threshold))]
    log_message(f"  Fold {fold_num + 1}: Threshold={threshold:.4f}, Sensitivity={sensitivity:.4f}, Specificity={specificity:.4f}")

mean_threshold = float(np.mean(best_model_results['fold_best_thresholds']))
log_message(f"\n✓ Threshold optimization complete for {best_model_name_for_deployment}")
log_message(f"  Mean threshold across folds: {mean_threshold:.4f}")

# ===== Markdown Cell 21 =====
# ## 11. Evaluation on Test Set

# ===== Cell 22 =====
# ====================================================================
# RETRAIN BEST MODEL ON FULL TRAIN SET, EVALUATE ON TEST SET
# ====================================================================
log_message(f"\n{'='*80}")
log_message(f"FINAL RETRAIN + TEST SET EVALUATION — {best_model_name_for_deployment}")
log_message(f"{'='*80}\n")

# Map best-model name → (base_model_fn, best_params_json_path)
_best_params_path_map = {
    model_name_efficientnet: (base_model_creators['EfficientNetB0'], best_params_path_eff),
    model_name_resnet:       (base_model_creators['ResNet50'],       best_params_path_res),
    model_name_convnext:     (base_model_creators['ConvNeXt-Tiny'],  best_params_path_cnx),
}
base_fn, best_params_path = _best_params_path_map[best_model_name_for_deployment]

with open(best_params_path, 'r') as _f:
    final_params = json.load(_f)
log_message(f"Loaded hyperparameters from {best_params_path}")

# Full train set = everything NOT in test_indices
_train_mask = np.ones(len(y_full), dtype=bool)
_train_mask[test_indices] = False
X_train_full = X_full[_train_mask]
y_train_full = y_full[_train_mask]
log_message(f"Full train set: {len(y_train_full)} | Test set: {len(y_test)}")

# Small internal val split for early stopping (do NOT use X_test here)
from sklearn.model_selection import train_test_split
X_tr, X_int_val, y_tr, y_int_val = train_test_split(
    X_train_full, y_train_full,
    test_size=0.1,
    stratify=y_train_full,
    random_state=SEED
)
log_message(f"Retrain split: train={len(y_tr)}, internal-val={len(y_int_val)}")

final_ckpt = os.path.join(
    CONFIG['checkpoint_dir'],
    f"{best_model_name_for_deployment}_FINAL.keras"
)

if os.path.exists(final_ckpt):
    log_message(f"✓ Final checkpoint found — loading from {final_ckpt}")
    final_model = tf.keras.models.load_model(final_ckpt)
else:
    log_message(f"Training final model on full train set...")
    base_model = base_fn()
    final_trainer = DFUModelTrainer(
        model_name=f"{best_model_name_for_deployment}_FINAL",
        base_model=base_model,
        dropout_rate=final_params['dropout_rate'],
        l2_reg=final_params['l2_reg'],
        dense_units=(final_params['dense_units_1'], final_params['dense_units_2'])
    )
    final_trainer.build_model()

    final_trainer.train_phase1(
        X_tr, y_tr, X_int_val, y_int_val,
        batch_size=final_params['batch_size'],
        optimizer=final_params['optimizer'],
        learning_rate=final_params['phase1_lr'],
        max_epochs=CONFIG['max_epochs'],
        patience=CONFIG['phase1_patience'],
        verbose=1
    )
    final_trainer.train_phase2(
        X_tr, y_tr, X_int_val, y_int_val,
        batch_size=final_params['batch_size'],
        optimizer=final_params['optimizer'],
        learning_rate=final_params['phase2_lr'],
        max_epochs=CONFIG['max_epochs'],
        patience=CONFIG['phase2_patience'],
        verbose=1
    )
    final_trainer.save_model(final_ckpt)
    final_model = final_trainer.model
    del final_trainer, base_model
    gc.collect()

# Predict on held-out test set
test_probs = final_model.predict(X_test, verbose=0).flatten()
y_pred_binary = (test_probs >= mean_threshold).astype(int)

# Metrics
_tn = int(np.sum((y_pred_binary == 0) & (y_test == 0)))
_fp = int(np.sum((y_pred_binary == 1) & (y_test == 0)))
_tp = int(np.sum((y_pred_binary == 1) & (y_test == 1)))
_fn = int(np.sum((y_pred_binary == 0) & (y_test == 1)))
_specificity = _tn / (_tn + _fp) if (_tn + _fp) > 0 else 0.0
_ppv = _tp / (_tp + _fp) if (_tp + _fp) > 0 else 0.0
_npv = _tn / (_tn + _fn) if (_tn + _fn) > 0 else 0.0

final_metrics = {
    'model':        best_model_name_for_deployment,
    'threshold':    mean_threshold,
    'accuracy':     accuracy_score(y_test, y_pred_binary),
    'precision':    precision_score(y_test, y_pred_binary, zero_division=0),
    'recall':       recall_score(y_test, y_pred_binary, zero_division=0),
    'sensitivity':  recall_score(y_test, y_pred_binary, zero_division=0),
    'specificity':  _specificity,
    'ppv':          _ppv,
    'npv':          _npv,
    'f1':           f1_score(y_test, y_pred_binary, zero_division=0),
    'auc_roc':      roc_auc_score(y_test, test_probs),
}

log_message(f"\n{'='*80}")
log_message(f"TEST SET METRICS — {best_model_name_for_deployment} (threshold={mean_threshold:.4f})")
log_message(f"{'='*80}")
for k, v in final_metrics.items():
    if isinstance(v, float):
        log_message(f"  {k:12s}: {v:.4f}")
    else:
        log_message(f"  {k:12s}: {v}")
log_message(f"\nConfusion Matrix:\n{confusion_matrix(y_test, y_pred_binary)}")
log_message(f"\nClassification Report:\n{classification_report(y_test, y_pred_binary, digits=4, zero_division=0)}")

# Save
results_df = pd.DataFrame([final_metrics]).set_index('model')
results_csv_path = os.path.join(CONFIG['results_dir'], 'final_test_results.csv')
results_df.to_csv(results_csv_path)
log_message(f"✓ Results saved to {results_csv_path}")

log_message(f"\n✓ Evaluation complete")