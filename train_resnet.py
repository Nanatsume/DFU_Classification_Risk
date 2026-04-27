"""Train ResNet50 only (Optuna + 5-fold CV). Resume-aware."""
from dfu_common import train_one_model, base_model_creators, make_logger

if __name__ == '__main__':
    log = make_logger('train_resnet')
    train_one_model('ResNet50', base_model_creators()['ResNet50'], log=log)
