"""Train ConvNeXt-Tiny only (GPyOpt + 5-fold CV). Resume-aware.

ConvNeXt-Tiny uses batch_size=32 (instead of global 64) to avoid OOM
during full fine-tuning of its larger feature maps (14x14x384).
"""
import dfu_common
from dfu_common import train_one_model, base_model_creators, make_logger

if __name__ == '__main__':
    dfu_common.CONFIG['batch_size_default'] = 32
    log = make_logger('train_convnext')
    train_one_model('ConvNeXt-Tiny', base_model_creators()['ConvNeXt-Tiny'], log=log)
