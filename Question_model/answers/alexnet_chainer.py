import chainer
import chainer.links as L
import chainer.functions as F
import argparse
import cv2
import numpy as np
from glob import glob

num_classes = 2
img_height, img_width = 227, 227
GPU = -1

class Mynet(chainer.Chain):
    def __init__(self, train=True):
        self.train = train
        super(Mynet, self).__init__()
        with self.init_scope():
            self.conv1 = L.Convolution2D(None, 96, ksize=11, pad=0, stride=4, nobias=False)
            self.conv2 = L.Convolution2D(None, 256, ksize=5, pad=1, nobias=False)
            self.conv3 = L.Convolution2D(None, 384, ksize=3, pad=1, nobias=False)
            self.conv4 = L.Convolution2D(None, 384, ksize=3, pad=1, nobias=False)
            self.conv5 = L.Convolution2D(None, 256, ksize=3, pad=1, nobias=False)
            self.fc1 = L.Linear(None, 4096, nobias=False)
            self.fc2 = L.Linear(None, 4096, nobias=False)
            self.fc_out = L.Linear(None, num_classes, nobias=False)

    def __call__(self, x):
        x = F.relu(self.conv1(x))
        x = F.local_response_normalization(x)
        x = F.max_pooling_2d(x, ksize=3, stride=2)
        x = F.relu(self.conv2(x))
        x = F.local_response_normalization(x)
        x = F.max_pooling_2d(x, ksize=3, stride=2)
        x = F.relu(self.conv3(x))
        x = F.relu(self.conv4(x))
        x = F.relu(self.conv5(x))
        
        x = F.relu(self.fc1(x))
        x = F.dropout(x)
        x = F.relu(self.fc2(x))
        x = F.dropout(x)
        x = self.fc_out(x)
        return x


# get train data
def data_load(path, hf=False, vf=False):
    xs = np.ndarray((0, img_height, img_width, 3), dtype=np.float32)
    ts = np.ndarray((0), dtype=np.int)
    paths = []
    
    for dir_path in glob(path + '/*'):
        for path in glob(dir_path + '/*'):
            x = cv2.imread(path)
            x = cv2.resize(x, (img_width, img_height)).astype(np.float32)
            x /= 255.
            xs = np.r_[xs, x[None, ...]]

            t = np.zeros((1))
            if 'akahara' in path:
                t = np.array((0), dtype=np.int)
            elif 'madara' in path:
                t = np.array((1), dtype=np.int)
            ts = np.r_[ts, t]

            paths.append(path)

            if hf:
                xs = np.r_[xs, x[:, ::-1][None, ...]]
                ts = np.r_[ts, t]
                paths.append(path)

            if vf:
                xs = np.r_[xs, x[::-1][None, ...]]
                ts = np.r_[ts, t]
                paths.append(path)

            if hf and vf:
                xs = np.r_[xs, x[::-1, ::-1][None, ...]]
                ts = np.r_[ts, t]
                paths.append(path)

    xs = xs.transpose(0,3,1,2)

    return xs, ts, paths


# train
def train():
    # model
    model = Mynet(train=True)

    if GPU >= 0:
        chainer.cuda.get_device(GPU).use()
        model.to_gpu()
    
    opt = chainer.optimizers.MomentumSGD(0.01, momentum=0.9)
    opt.setup(model)
    opt.add_hook(chainer.optimizer.WeightDecay(0.0005))

    xs, ts, _ = data_load('../Dataset/train/images/', hf=True, vf=True)

    # training
    mb = 8
    mbi = 0
    train_ind = np.arange(len(xs))
    np.random.seed(0)
    np.random.shuffle(train_ind)
    
    for i in range(500):
        if mbi + mb > len(xs):
            mb_ind = train_ind[mbi:]
            np.random.shuffle(train_ind)
            mb_ind = np.hstack((mb_ind, train_ind[:(mb-(len(xs)-mbi))]))
            mbi = mb - (len(xs) - mbi)
        else:
            mb_ind = train_ind[mbi: mbi+mb]
            mbi += mb

        x = xs[mb_ind]
        t = ts[mb_ind]
            
        if GPU >= 0:
            x = chainer.cuda.to_gpu(x)
            t = chainer.cuda.to_gpu(t)
        #else:
        #    x = chainer.Variable(x)
        #    t = chainer.Variable(t)

        y = model(x)

        loss = F.softmax_cross_entropy(y, t)
        accu = F.accuracy(y, t)

        model.cleargrads()
        loss.backward()
        opt.update()

        loss = loss.data
        accu = accu.data
        if GPU >= 0:
            loss = chainer.cuda.to_cpu(loss)
            accu = chainer.cuda.to_cpu(accu)
        
        print("iter >>", i+1, ',loss >>', loss.item(), ',accuracy >>', accu)

    chainer.serializers.save_npz('cnn.npz', model)

# test
def test():
    model = Mynet(train=False)

    if GPU >= 0:
        chainer.cuda.get_device_from_id(cf.GPU).use()
        model.to_gpu()

    ## Load pretrained parameters
    chainer.serializers.load_npz('cnn.npz', model)

    xs, ts, paths = data_load('../Dataset/test/images/')

    for i in range(len(paths)):
        x = xs[i]
        t = ts[i]
        path = paths[i]
        x = np.expand_dims(x, axis=0)
        
        if GPU >= 0:
            x = chainer.cuda.to_gpu(x)
            
        pred = model(x).data
        pred = F.softmax(pred)

        if GPU >= 0:
            pred = chainer.cuda.to_cpu(pred)
                
        pred = pred[0].data
                
        print("in {}, predicted probabilities >> {}".format(path, pred))
    

def arg_parse():
    parser = argparse.ArgumentParser(description='CNN implemented with Keras')
    parser.add_argument('--train', dest='train', action='store_true')
    parser.add_argument('--test', dest='test', action='store_true')
    args = parser.parse_args()
    return args

# main
if __name__ == '__main__':
    args = arg_parse()

    if args.train:
        train()
    if args.test:
        test()

    if not (args.train or args.test):
        print("please select train or test flag")
        print("train: python main.py --train")
        print("test:  python main.py --test")
        print("both:  python main.py --train --test")
