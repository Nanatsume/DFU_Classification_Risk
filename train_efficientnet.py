"""Train EfficientNetB0 only (Optuna + 5-fold CV). Resume-aware."""
from dfu_common import train_one_model, base_model_creators, make_logger

if __name__ == '__main__':
    log = make_logger('train_efficientnet')
    train_one_model('EfficientNetB0', base_model_creators()['EfficientNetB0'], log=log)
