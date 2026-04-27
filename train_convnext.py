"""Train ConvNeXt-Tiny only (Optuna + 5-fold CV). Resume-aware."""
from dfu_common import train_one_model, base_model_creators, make_logger

if __name__ == '__main__':
    log = make_logger('train_convnext')
    train_one_model('ConvNeXt-Tiny', base_model_creators()['ConvNeXt-Tiny'], log=log)
