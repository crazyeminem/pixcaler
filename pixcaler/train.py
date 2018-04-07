import matplotlib
matplotlib.use('Agg')


import argparse
import os

import chainer
from chainer import training
from chainer.training import extensions
from chainer import serializers
from chainerui.utils import save_args
from chainerui.extensions import CommandsExtension

from pixcaler.net import Discriminator
from pixcaler.net import Generator
from pixcaler.updater import Pix2PixUpdater
from pixcaler.dataset import PairDownscaleDataset, AutoUpscaleDataset, AutoUpscaleDatasetReverse
from pixcaler.visualizer import out_image

def main():
    parser = argparse.ArgumentParser(
        description='chainer implementation of pix2pix',
    )
    parser.add_argument(
        '--batchsize', '-b', type=int, default=1,
        help='Number of images in each mini-batch',
    )
    parser.add_argument(
        '--epoch', '-e', type=int, default=200,
        help='Number of sweeps over the dataset to train',
    )
    parser.add_argument(
        '--base_ch', type=int, default=64,
        help='base channel size of hidden layer',
    )
    parser.add_argument(
        '--gpu', '-g', type=int, default=-1,
        help='GPU ID (negative value indicates CPU)',
    )
    parser.add_argument(
        '--dataset', '-i', default='./image/fsm',
        help='Directory of image files.',
    )
    parser.add_argument(
        '--out', '-o', default='result',
        help='Directory to output the result',
    )
    parser.add_argument(
        '--resume', '-r', default='',
        help='Resume the training from snapshot',
    )
    parser.add_argument(
        '--snapshot_interval', type=int, default=1000,
        help='Interval of snapshot',
    )
    parser.add_argument(
        '--display_interval', type=int, default=10,
        help='Interval of displaying log to console',
    )
    parser.add_argument(
        '--preview_interval', type=int, default=100,
        help='Interval of previewing generated image',    
    )
    parser.add_argument(
        '--mode', required=True, choices=('up', 'down'),
        help='training mode',
    )
    parser.add_argument(
        '--use_random_nn_downscale', action='store_true', default=False,
        help='downscal by sampling 4-nearest pixel randomly',
    )
    args = parser.parse_args()
    save_args(args, args.out)

    print('GPU: {}'.format(args.gpu))
    print('# Minibatch-size: {}'.format(args.batchsize))
    print('# epoch: {}'.format(args.epoch))
    print('')

    gen = Generator(in_ch=4, out_ch=4, base_ch=args.base_ch)
    dis = Discriminator(in_ch=4, out_ch=4, base_ch=args.base_ch)
    
    if args.gpu >= 0:
        chainer.cuda.get_device(args.gpu).use()  # Make a specified GPU current
        gen.to_gpu()  # Copy the model to the GPU
        dis.to_gpu()

    # Setup an optimizer
    def make_optimizer(model, alpha=0.0002, beta1=0.5):
        optimizer = chainer.optimizers.Adam(alpha=alpha, beta1=beta1)
        optimizer.setup(model)
        optimizer.add_hook(chainer.optimizer.WeightDecay(0.00001), 'hook_dec')
        return optimizer
    opt_enc = make_optimizer(gen.enc)
    opt_dec = make_optimizer(gen.dec)
    opt_dis = make_optimizer(dis)

    if args.mode == 'up':
        print('# upscale learning with automatically generated images')
        train_d = AutoUpscaleDataset(
            "{}/main".format(args.dataset),
            random_nn=args.use_random_nn_downscale,
        )
        test_d = AutoUpscaleDataset(
            "{}/test".format(args.dataset),        
            random_nn=False,
        )
    elif args.mode == 'down':
        print('# downscale learning')
        train_d = PairDownscaleDataset(
            "{}/main/target".format(args.dataset),
            "{}/main/source".format(args.dataset),            
        )
        test_d = AutoUpscaleDatasetReverse(
            "{}/test".format(args.dataset),
        )

    train_iter = chainer.iterators.SerialIterator(train_d, args.batchsize)
    test_iter = chainer.iterators.SerialIterator(test_d, args.batchsize)

    # Set up a trainer
    updater = Pix2PixUpdater(
        models=(gen, dis),
        iterator={
            'main': train_iter,
            'test': test_iter,
        },
        optimizer={
            'enc': opt_enc,
            'dec': opt_dec, 
            'dis': opt_dis,
        },
        device=args.gpu)
    trainer = training.Trainer(updater, (args.epoch, 'epoch'), out=args.out)

    snapshot_interval = (args.snapshot_interval, 'iteration')
    display_interval = (args.display_interval, 'iteration')
    preview_interval = (args.preview_interval, 'iteration')
    
    trainer.extend(extensions.snapshot(
        filename='snapshot_iter_{.updater.iteration}.npz'),
        trigger=snapshot_interval,
    )
    trainer.extend(extensions.snapshot_object(
        gen, 'gen_iter_{.updater.iteration}.npz'),
        trigger=snapshot_interval,
    )
    trainer.extend(extensions.snapshot_object(
        dis, 'dis_iter_{.updater.iteration}.npz'),
        trigger=snapshot_interval,
    )
    trainer.extend(extensions.LogReport(trigger=preview_interval))
    trainer.extend(extensions.PlotReport(
        ['enc/loss_adv', 'enc/loss_rec', 'enc/loss', 'dis/loss',],
        trigger=preview_interval,
    ))
    trainer.extend(extensions.PrintReport([
        'epoch', 'iteration', 'enc/loss_adv', 'enc/loss_rec', 'enc/loss', 'dis/loss',
    ]), trigger=display_interval)
    trainer.extend(extensions.ProgressBar(update_interval=10))
    trainer.extend(out_image(gen, 8, args.out), trigger=preview_interval)
    trainer.extend(CommandsExtension())

    if args.resume:
        # Resume from a snapshot
        chainer.serializers.load_npz(args.resume, trainer)

    # Run the training
    trainer.run()

if __name__ == '__main__':
    main()