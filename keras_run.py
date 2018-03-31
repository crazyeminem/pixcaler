from pathlib import Path

import numpy as np
import fire
import math

import keras
import keras_model
import dataset
import chainer

class GeneratorVisualizer(keras.callbacks.Callback):
    def __init__(self, gen, test_iterator, n, out_dir):
        self.test_iterator = test_iterator
        self.n = n
        self.iteration = 0
        self.out_dir = Path(out_dir)
        self.epoch = 0
        self.gen = gen

    def on_epoch_begin(self, epoch, logs={}):
        self.epoch = epoch

    def on_batch_begin(self, batch, logs={}):
        self.iteration += 1

    def on_batch_end(self, batch, logs={}):
        n_pattern = 4
        n_images = self.n * n_pattern

        rows = self.n
        cols = n_pattern
        
        ret = []
        
        for it in range(n):
            x_in = test_iterator.next()
            x_in = x_in.transpose((0, 2, 3, 1)).reshape(x_in[1:])
            x_real = x_real.transpose((0, 2, 3, 1)).reshape(x_real[1:])
            x_out = self.model.get_layer('Generator').predicate(x_in)
    
            ret.append(x_in)
            ret.append(t_out)
            ret.append(x_out)
        
        def save_image(x, name, mode=None):
            _, C, H, W = x.shape
            x = x.reshape((rows, cols, C, H, W))
            x = x.transpose(0, 2, 1, 3, 4)
            if C==1:
                x = x.reshape((rows*H, cols*W))
            else:
                x = x.reshape((rows*H, cols*W, C))

            preview_dir = self.out_dir/'preview'
            preview_path = preview_dir/'image_{}_{:0>8}_{:0>8}.png'.format(name, self.epoch, self.iteration)
            current_path = preview_dir/'image_{}_cureent.png'.format(name)
            if not os.path.exists(preview_dir):
                os.makedirs(preview_dir)
            img = Image.fromarray(x, mode=mode).convert('RGBA')
            img.save(preview_path)
            img.save(current_path)
        max_h = max(r.shape[1] for r in ret)
        max_w = max(r.shape[2] for r in ret)
        x = np.asarray(np.clip(np.asarray(ret) * 127.5 + 127.5, 0.0, 255.0), dtype=np.uint8)
        save_image(x, "gen")

def train(
    label_dir,
    epochs=200,
    size=64,
    in_ch=4,
    out_ch=4,
    batch_size=1,
    display_iteration_interval=1,
    preview_iteration_interval=500,
    snapshot_epoch_interval=1,
    out_dir='result/'
):
    label_dir = Path(label_dir)
    out_dir = Path(out_dir)
    train_dataset = dataset.AutoUpscaleDataset(str(label_dir/'main'))
    train_iterator = chainer.iterators.SerialIterator(
        train_dataset,
        batch_size=batch_size,
    )
    
    test_iterator = chainer.iterators.SerialIterator(
        dataset.AutoUpscaleDataset(str(label_dir/'test')),
        batch_size=1,
    )

    def _dataset():
        for i, batch in enumerate(train_iterator):
            x_in = np.asarray([b[0] for b in batch]).astype('f')
            x_real = np.asarray([b[1] for b in batch]).astype('f')
            x_in = x_in.transpose((0, 2, 3, 1))
            x_real = x_real.transpose((0, 2, 3, 1))            
            yield [
                [
                    x_in,
                    x_real,
                ],
                [
                    x_real,
                    np.zeros((batch_size, size // 8, size // 8, 1)),
                    np.zeros((batch_size, size // 8, size // 8, 1)),
                    np.zeros((batch_size, size // 8, size // 8, 1)),
                ],
            ]

    trainer, generator = keras_model.pix2pix(size, in_ch, out_ch)
    trainer.compile(
        keras.optimizers.Adam(
            lr=0.0002,
            beta_1=0.5,
            beta_2=0.999,
            epsilon=1e-8,
            decay=0.0,
            amsgrad=False,
        ),
        [
            keras_model.gen_loss_l1(),
            keras_model.gen_loss_adv(),
            keras_model.dis_loss_real(),
            keras_model.dis_loss_fake(),        
        ],
    )
    trainer.fit_generator(
        _dataset(),
        math.ceil(len(train_dataset) / batch_size),
        epochs=epochs,
        verbose=1,
        callbacks=[
            keras.callbacks.ModelCheckpoint(
                str(out_dir/'model_{epoch:02d}.hdf5'),
                monitor='val_loss',
                verbose=0,
                save_best_only=False,
                save_weights_only=False,
                mode='auto',
                period=1,
            ),
            keras.callbacks.TensorBoard(
                log_dir=str(out_dir/'logs'),
                histogram_freq=0,
                batch_size=None,
                write_graph=True,
                write_grads=False,
                write_images=False,
                embeddings_freq=0,
                embeddings_layer_names=None,
                embeddings_metadata=None,
            ),
        ]
    )



if __name__ == '__main__':
    fire.Fire()