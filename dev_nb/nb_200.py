
        #################################################
        ### THIS FILE WAS AUTOGENERATED! DO NOT EDIT! ###
        #################################################
        # file to edit: dev_nb/200_datablock_config.ipynb

from fastai.datasets import URLs, untar_data
from pathlib import Path
import pandas as pd, numpy as np, torch, re, PIL, os, mimetypes, csv, itertools
import matplotlib.pyplot as plt
from collections import OrderedDict
from typing import *
from enum import Enum
from functools import partial,reduce
from torch import tensor
from IPython.core.debugger import set_trace

def ifnone(a, b): return b if a is None else a
def noop(x, *args, **kwargs): return x
def range_of(x): return list(range(len(x)))
torch.Tensor.ndim = property(lambda x: x.dim())

import operator

def test(a,b,cmp,cname=None):
    if cname is None: cname=cmp.__name__
    assert cmp(a,b),f"{cname}:\n{a}\n{b}"

def test_eq(a,b):    test(a,b,operator.eq,'==')
def test_ne(a,b):    test(a,b,operator.ne,'!=')
def test_equal(a,b): test(a,b,torch.equal,'==')
def test_np_eq(a,b): test(a,b,np.equal,'==')

def compose(*funcs): return reduce(lambda f,g: lambda x: f(g(x)), reversed(funcs), noop)

def listify(o):
    "Make `o` a list."
    if o is None: return []
    if isinstance(o, list): return o
    if isinstance(o, str): return [o]
    if not isinstance(o, Iterable): return [o]
    #Rank 0 tensors in PyTorch are Iterable but don't have a length.
    try: a = len(o)
    except: return [o]
    return list(o)

from inspect import getfullargspec

def has_param(func, p):
    "Check if `func` accepts `p` as argument."
    return p in getfullargspec(func).args

def feed_kwargs(func, *args, **kwargs):
    "Feed `args` and the `kwargs` `func` accepts to `func`."
    signature = getfullargspec(func)
    if signature.varkw is not None: return func(*args, **kwargs)
    passed_kwargs = {k:v for k,v in kwargs.items() if k in signature.args}
    return func(*args, **passed_kwargs)

def order_sorted(funcs, order_key='_order'):
    "Listify `funcs` and sort it with `order_key`."
    key = lambda o: getattr(o, order_key, 0)
    return sorted(listify(funcs), key=key)

def apply_all(x, funcs, *args, order_key='_order', filter_kwargs=False, **kwargs):
    "Apply all `funcs` to `x` in order, pass along `args` and `kwargs`."
    for f in order_sorted(funcs, order_key=order_key):
        x = feed_kwargs(f, x, *args, **kwargs) if filter_kwargs else f(x, *args, **kwargs)
    return x

def mask2idxs(mask): return [i for i,m in enumerate(mask) if m]

def uniqueify(x, sort=False, bidir=False):
    "Return the unique elements in `x`, optionally `sort`-ed, optionally return the reverse correspondance."
    res = list(OrderedDict.fromkeys(x).keys())
    if sort: res.sort()
    if bidir: return res, {v:k for k,v in enumerate(res)}
    return res

def setify(o): return o if isinstance(o,set) else set(listify(o))

def onehot(x, c, a=1.):
    "Return the `a`-hot encoded tensor for `x` with `c` classes."
    res = torch.zeros(c)
    if a<1: res += (1-a)/(c-1)
    res[x] = a
    return res

def _get_files(p, fs, extensions=None):
    p = Path(p)
    res = [p/f for f in fs if not f.startswith('.')
           and ((not extensions) or f'.{f.split(".")[-1].lower()}' in extensions)]
    return res

def get_files(path, extensions=None, recurse=False, include=None):
    "Get all the files in `path` with optional `extensions`."
    path = Path(path)
    extensions = setify(extensions)
    extensions = {e.lower() for e in extensions}
    if recurse:
        res = []
        for i,(p,d,f) in enumerate(os.walk(path)): # returns (dirpath, dirnames, filenames)
            if include is not None and i==0: d[:] = [o for o in d if o in include]
            else:                            d[:] = [o for o in d if not o.startswith('.')]
            res += _get_files(p, f, extensions)
    else:
        f = [o.name for o in os.scandir(path) if o.is_file()]
        res = _get_files(path, f, extensions)
    return res

class DataSource():
    def __init__(self, items, tfms=None, filters=None, **tfm_kwargs):
        if filters is None: filters = [range(len(items))]
        if isinstance(filters[0][0], bool): filters = [mask2idxs(filt) for filt in filters]
        self.items,self.filters,self.tfms = listify(items),listify(filters),[]
        self.tfm_kwargs = tfm_kwargs
        tfms = order_sorted(tfms)
        for tfm in tfms:
            getattr(tfm, 'setup', noop)(self)
            self.tfms.append(tfm)

    def transformed(self, tfms, **tfm_kwargs):
        tfms = listify(tfms)
        tfm_kwargs = {**self.tfm_kwargs, **tfm_kwargs}
        return self.__class__(self.items, self.tfms + tfms, self.filters, **tfm_kwargs)

    def __len__(self): return len(self.filters)
    def len(self, filt=0): return len(self.filters[filt])
    def __getitem__(self, i): return FilteredList(self, i)

    def sublist(self, filt):
        return [self.get(j,filt) for j in range(self.len(filt))]

    def get(self, idx, filt=0):
        if hasattr(idx,'__len__') and getattr(idx,'ndim',1):
            # rank>0 collection
            if isinstance(idx[0],bool):
                assert len(idx)==self.len(filt) # bool mask
                return [self.get(i,filt) for i,m in enumerate(idx) if m]
            return [self.get(i,filt) for i in idx]  # index list
        if self.filters: idx = self.filters[filt][idx]
        res = self.items[idx]
        if self.tfms: res = apply_all(res, self.tfms, filt=filt, filter_kwargs=True, **self.tfm_kwargs)
        return res

    def decode(self, o, filt=0):
        if self.tfms:
            return apply_all(o, [getattr(f, 'decode', noop) for f in reversed(self.tfms)],
                             filt=filt, filter_kwargs=True, **self.tfm_kwargs)

    def __iter__(self):
        for i in range_of(self.filters):
            yield (self.get(j,i) for j in range(self.len(i)))

    def __eq__(self,b):
        if not isinstance(b,DataSource): b = DataSource(b)
        if len(b) != len(self): return False
        for i in range_of(self.filters):
            if b.len(i) != self.len(i): return False
            return all(self.get(j,i)==b.get(j,i) for j in range_of(self.filters[i]))

    def __repr__(self):
        res = f'{self.__class__.__name__}\n'
        for i,o in enumerate(self):
            l = self.len(i)
            res += f'{i}: ({l} items) ['
            res += ','.join(itertools.islice(map(str,o), 10))
            if l>10: res += '...'
            res += ']\n'
        return res

    @property
    def train(self): return self[0]
    @property
    def valid(self): return self[1]

class FilteredList:
    def __init__(self, il, filt): self.il,self.filt = il,filt
    def __getitem__(self,i): return self.il.get(i,self.filt)
    def __len__(self): return self.il.len(self.filt)

    def __iter__(self):
        return (self.il.get(j,self.filt) for j in range_of(self))

    def __repr__(self):
        res = f'({len(self)} items) ['
        res += ','.join(itertools.islice(map(str,self), 10))
        if len(self)>10: res += '...'
        res += ']\n'
        return res

    def decode(self, o): return self.il.decode(o, self.filt)

class Transform():
    _order = 0
    def setup(self, data): return    # 1-time setup
    def __call__(self,o):  return o  # transform
    def decode(self,o):    return o  # reverse transform for display

def _get_show_func(tfms):
    for t in reversed(tfms):
        if hasattr(t, 'show') and t.show is not None: return t.show
    return None

def show_xy(x, y, show_x, show_y, **kwargs):
    # can pass func or obj with a `show` method
    show_x = getattr(show_x, 'show', show_x)
    show_y = getattr(show_y, 'show', show_y)
    kwargs['ax'] = feed_kwargs(show_x, x, **kwargs)
    feed_kwargs(show_y, y, **kwargs)

class TupleTransform():
    def __init__(self, *tfms): self.tfms = [order_sorted(tfm) for tfm in listify(tfms)]
    def __call__(self, o, filt=0, **kwargs):
        return [apply_all(o, tfm, filt=filt, filter_kwargs=True, **kwargs) for tfm in self.tfms]
    def decode(self, o, filt=0, **kwargs):
        return [apply_all(x, [getattr(f, 'decode', noop) for f in reversed(tfm)], filt=filt,
                          filter_kwargs=True, **kwargs)
                for x,tfm in zip(o,self.tfms)]

    def setup(self, data):
        old_tfms = getattr(data, 'tfms', []).copy()
        for tfm in self.tfms:
            for t in tfm:
                getattr(t, 'setup', noop)(data)
                data.tfms.append(t)
            data.tfms = old_tfms.copy()

    def show(self, o, show_x=None, show_y=None, **kwargs):
        if show_x is None: show_x=_get_show_func(self.tfms[0])
        if show_y is None: show_y=_get_show_func(self.tfms[1])
        show_xy(*o, show_x, show_y, **kwargs)

image_extensions = set(k for k,v in mimetypes.types_map.items() if v.startswith('image/'))

def get_image_files(path, include=None):
    "Get image files in `path` recursively."
    return get_files(path, extensions=image_extensions, recurse=True, include=include)

def random_splitter(items, valid_pct=0.2, seed=None):
    "Split `items` between train/val with `valid_pct` randomly."
    if seed is not None: torch.manual_seed(seed)
    rand_idx = torch.randperm(len(items))
    cut = int(valid_pct * len(items))
    return rand_idx[cut:],rand_idx[:cut]

def _grandparent_mask(items, name):
    return [(o.parent.parent.name if isinstance(o, Path) else o.split(os.path.sep)[-2]) == name for o in items]

def grandparent_splitter(items, train_name='train', valid_name='valid'):
    "Split `items` from the grand parent folder names (`train_name` and `valid_name`)."
    return _grandparent_mask(items, train_name),_grandparent_mask(items, valid_name)

def parent_label(o):
    "Label `item` with the parent folder name."
    return o.parent.name if isinstance(o, Path) else o.split(os.path.sep)[-1]

def re_labeller(pat):
    "Label `item` with regex `pat`."
    pat = re.compile(pat)
    def _inner(o):
        res = pat.search(str(o))
        assert res,f'Failed to find "{pat}" in "{o}"'
        return res.group(1)
    return _inner

def show_image(im, ax=None, figsize=None, **kwargs):
    "Show a PIL image on `ax`."
    if ax is None: _,ax = plt.subplots(figsize=figsize)
    ax.imshow(im, **kwargs)
    ax.axis('off')
    return ax

class Imagify(Transform):
    def __init__(self, f=PIL.Image.open, cmap=None, alpha=1.): self.f,self.cmap,self.alpha = f,cmap,alpha
    def __call__(self, fn): return PIL.Image.open(fn)
    def show(self, im, ax=None, figsize=None, cmap=None, alpha=None):
        cmap = ifnone(cmap,self.cmap)
        alpha = ifnone(alpha,self.alpha)
        return show_image(im, ax, figsize=figsize, cmap=cmap, alpha=alpha)

class Categorize(Transform):
    _order=1
    def __init__(self):   self.vocab = None
    def __call__(self,o): return self.o2i[o]
    def decode(self, o):  return self.vocab[o]
    def show(self, o, ax=None):
        if ax is None: print(o)
        else: ax.set_title(o)

    def setup(self, items):
        if self.vocab is not None: return
        vals = [o for o in items.train]
        self.vocab,self.o2i = uniqueify(vals, sort=True, bidir=True)

def _ds_show(self, o, filt=0, show_func=None, **kwargs):
    o = self.decode(o, filt)
    if show_func is None: show_func=_get_show_func(self.tfms)
    show_func(o, **kwargs)

DataSource.show = _ds_show

def _fl_show(self, o, show_func=None, **kwargs):
    o = self.decode(o)
    if show_func is None: show_func=_get_show_func(self.il.tfms)
    show_func(o, **kwargs)

FilteredList.show = _fl_show

TfmY = Enum('TfmY', 'Mask Image Point Bbox No')

class ImageTransform():
    "Basic class for image transforms."
    _order=10
    _data_aug=False
    _tfm_y_func={TfmY.Image: 'apply_img',   TfmY.Mask: 'apply_mask', TfmY.No: 'noop',
                 TfmY.Point: 'apply_point', TfmY.Bbox: 'apply_bbox'}
    _decode_y_func={TfmY.Image: 'unapply_img',   TfmY.Mask: 'unapply_mask', TfmY.No: 'noop',
                   TfmY.Point: 'unapply_point', TfmY.Bbox: 'unapply_bbox'}

    def randomize(self): pass

    def __call__(self, o, filt=0, **kwargs):
        if self._data_aug and filt != 0: return o
        x,y = o
        self.x,self.filt = x,filt # Saves the x in case it's needed in the apply for y and filt
        self.randomize() # Ensures we have the same state for x and y
        return self.apply(x),self.apply_y(y, **kwargs)

    def decode(self, o, filt=0, **kwargs):
        if self._data_aug and filt != 0: return o
        (x,y) = o
        self.x,self.filt = x,filt
        return self.unapply(x),self.unapply_y(y, **kwargs)

    def noop(self,x):         return x
    def apply_img(self, y):   return self.apply(y)
    def apply_mask(self, y):  return self.apply_img(y)
    def apply_point(self, y): return y
    def apply_bbox(self, y):  return self.apply_point(y)

    def apply(self, x): return x
    def apply_y(self, y, tfm_y=TfmY.No):
        return getattr(self, self._tfm_y_func[tfm_y])(y)

    def unapply_img(self, y):   return self.unapply(y)
    def unapply_mask(self, y):  return self.unapply_img(y)
    def unapply_point(self, y): return y
    def unapply_bbox(self, y):  return self.unapply_point(y)

    def unapply(self, x): return x
    def unapply_y(self, y, tfm_y=TfmY.No):
        return getattr(self, self._decode_y_func[tfm_y])(y)

class DecodeImg(ImageTransform):
    "Convert regular image to RGB, masks to L mode."
    def __init__(self, mode_x='RGB', mode_y=None): self.mode_x,self.mode_y = mode_x,mode_y
    def apply(self, x):       return x.convert(self.mode_x)
    def apply_image(self, y): return y.convert(ifnone(self.mode_y,self.mode_x))
    def apply_mask(self, y):  return y.convert(ifnone(self.mode_y,'L'))

class ResizeFixed(ImageTransform):
    "Resize image to `size` using `mode_x` (and `mode_y` on targets)."
    _order=15
    def __init__(self, size, mode_x=PIL.Image.BILINEAR, mode_y=None):
        if isinstance(size,int): size=(size,size)
        size = (size[1],size[0]) #PIL takes size in the otherway round
        self.size,self.mode_x,self.mode_y = size,mode_x,mode_y

    def apply(self, x):       return x.resize(self.size, self.mode_x)
    def apply_image(self, y): return y.resize(self.size, ifnone(self.mode_y,self.mode_x))
    def apply_mask(self, y):  return y.resize(self.size, ifnone(self.mode_y,PIL.Image.NEAREST))

class ToByteTensor(ImageTransform):
    "Transform our items to byte tensors."
    _order=20
    def apply(self, x):
        res = torch.ByteTensor(torch.ByteStorage.from_buffer(x.tobytes()))
        w,h = x.size
        return res.view(h,w,-1).permute(2,0,1)

    def unapply(self, x):
        x = torch.clamp(x, 0, 1)
        return x[0] if x.shape[0] == 1 else x.permute(1,2,0)

class ToFloatTensor(ImageTransform):
    "Transform our items to float tensors (int in the case of mask)."
    _order=20
    def __init__(self, div_x=255., div_y=None): self.div_x,self.div_y = div_x,div_y
    def apply(self, x): return x.float().div_(self.div_x)
    def apply_mask(self, x):
        return x.long() if self.div_y is None else x.long().div_(self.div_y)

class TransformedDataLoader():
    def __init__(self, dl, tfms=None, **tfm_kwargs):
        self.dl,self.tfms,self.tfm_kwargs = dl,order_sorted(tfms),tfm_kwargs

    def __len__(self): return len(self.dl)
    def __iter__(self):
        for b in self.dl: yield apply_all(b, self.tfms, filter_kwargs=True, **self.tfm_kwargs)

    def decode(self, o):
        return apply_all(o, [getattr(f, 'decode', noop) for f in reversed(self.tfms)],
                         filter_kwargs=True, **self.tfm_kwargs)

    @property
    def dataset(self): return self.dl.dataset

from torch.utils.data.dataloader import DataLoader

def get_dls(il, bs=64, tfms=None, **tfm_kwargs):
    return [TransformedDataLoader(DataLoader(il[i], bs, shuffle=i==0), tfms=tfms, **tfm_kwargs) for i in range_of(il)]

def grab_item(b,k):
    if isinstance(b, (list,tuple)): return [grab_item(o,k) for o in b]
    return b[k]

class DataBunch():
    "Basic wrapper around several `DataLoader`s."
    def __init__(self, *dls): self.dls = dls
    def one_batch(self, i): return next(iter(self.dls[i]))

    @property
    def train_dl(self): return self.dls[0]
    @property
    def valid_dl(self): return self.dls[1]
    @property
    def train_ds(self): return self.train_dl.dataset
    @property
    def valid_ds(self): return self.valid_dl.dataset

    def show_batch(self, i=0, items=9, cols=3, figsize=None, show_func=None, **kwargs):
        b = self.dls[i].decode(self.one_batch(i))
        rows = (items+cols-1) // cols
        if figsize is None: figsize = (cols*3, rows*3)
        fig,axs = plt.subplots(rows, cols, figsize=figsize)
        for k,ax in enumerate(axs.flatten()):
            self.dls[i].dataset.show(grab_item(b,k), ax=ax, show_func=show_func, **kwargs)

def _ds_databunch(self, bs=64, tfms=None, **tfm_kwargs):
    dls = get_dls(self, bs=bs, tfms=tfms, **tfm_kwargs)
    return DataBunch(*dls)

DataSource.databunch = _ds_databunch

class Normalize(Transform):
    def __init__(self, mean, std, do_x=True, do_y=False):
        self.mean,self.std,self.do_x,self.do_y = mean,std,do_x,do_y

    def __call__(self, b):
        x,y = b
        if self.do_x: x = self.normalize(x)
        if self.do_y: y = self.normalize(y)
        return x,y

    def decode(self, b):
        x,y = b
        if self.do_x: x = self.denorm(x)
        if self.do_y: y = self.denorm(y)
        return x,y

    def normalize(self, x): return (x - self.mean) / self.std
    def denorm(self, x):    return x * self.std + self.mean

class Item():
    default_tfm = None
    default_tfm_ds = None
    default_tfm_kwargs = None

class DataBlock():
    type_cls = (Item,Item)
    def get_source(self):        raise NotImplementedError
    def get_items(self, source): raise NotImplementedError
    def split(self, items):      raise NotImplementedError
    def label_func(self, item):  raise NotImplementedError

    def __init__(self, tfms_x=None, tfms_y=None, tfms_ds=None):
        (x,y) = self.type_cls
        self.tfms_x = [t() for t in listify(x.default_tfm)] if tfms_x is None else tfms_x
        self.tfms_y = [t() for t in listify(y.default_tfm)] if tfms_y is None else tfms_y
        if tfms_ds is None:
            tfms_ds = [t() for t in listify(x.default_tfm_ds) + listify(y.default_tfm_ds)]
        self.tfms_ds = tfms_ds
        self.tfm_kwargs = {**ifnone(x.default_tfm_kwargs, {}), **ifnone(y.default_tfm_kwargs, {}) }

    def datasource(self, tfms=None, **tfm_kwargs):
        source = self.get_source()
        items = self.get_items(source)
        split_idx = self.split(items)
        ds = DataSource(items, TupleTransform(self.tfms_x, [self.label_func] + listify(self.tfms_y)), split_idx)
        ds = ds.transformed(self.tfms_ds + listify(tfms), **{**self.tfm_kwargs, **tfm_kwargs})
        return ds

    def databunch(self, ds_tfms=None, dl_tfms=None, bs=64, **tfm_kwargs):
        dls = get_dls(self.datasource(tfms=ds_tfms, **tfm_kwargs), bs, tfms=dl_tfms,
                      **{**self.tfm_kwargs, **tfm_kwargs})
        return DataBunch(*dls)

class Image(Item):
    default_tfm = Imagify

class Category(Item):
    default_tfm = Categorize

class MultiCategorize(Transform):
    _order=1
    def __init__(self): self.vocab = None
    def __call__(self,x): return [self.o2i[o] for o in x if o in self.o2i]
    def decode(self, o):  return [self.vocab[i] for i in o]
    def show(self, o, ax=None):
        (print if ax is None else ax.set_title)(';'.join(o))

    def setup(self, items):
        if self.vocab is not None: return
        vals = set()
        for c in items.train: vals = vals.union(set(c))
        vals = list(vals)
        self.vocab,self.o2i = uniqueify(vals, sort=True, bidir=True)

class OneHotEncode(Transform):
    _order=10
    def setup(self, items):
        self.c = None
        for tfm in items.tfms:
            if isinstance(tfm, MultiCategorize): self.c = len(tfm.vocab)

    def __call__(self, o): return onehot(o, self.c) if self.c is not None else o
    def decode(self, o):   return [i for i,x in enumerate(o) if x == 1]

class MultiCategory(Item):
    default_tfm = [MultiCategorize, OneHotEncode]

def get_str_column(df, col_name, prefix='', suffix='', delim=None):
    "Read `col_name` in `df`, optionnally adding `prefix` or `suffix`."
    values = df[col_name].values.astype(str)
    values = np.char.add(np.char.add(prefix, values), suffix)
    if delim is not None:
        values = np.array(list(csv.reader(values, delimiter=delim)))
    return values

class SegmentMask(Item):
    default_tfm = partial(Imagify, cmap='tab20', alpha=0.5)
    default_tfm_kwargs = {'tfm_y': TfmY.Mask}

class PointScaler(Transform):
    _order = 5 #Run before we apply any ImageTransform
    def __init__(self, do_scale=True, y_first=False):
        self.do_scale,self.y_first = do_scale,y_first

    def __call__(self, o, tfm_y=TfmY.No):
        (x,y) = o
        if not isinstance(y, torch.Tensor): y = tensor(y)
        y = y.view(-1, 2).float()
        if not self.y_first: y = y.flip(1)
        if self.do_scale: y = y * 2/tensor(list(x.size)).float() - 1
        return (x,y)

    def decode(self, o, tfm_y=TfmY.No):
        (x,y) = o
        y = y.flip(1)
        y = (y + 1) * tensor([x.shape[:2]]).float()/2
        return (x,y)

class PointShow(Transform):
    def show(self, x, ax=None):
        params = {'s': 10, 'marker': '.', 'c': 'r'}
        ax.scatter(x[:, 1], x[:, 0], **params)

class Points(Item):
    default_tfm = PointShow
    default_tfm_ds = PointScaler
    default_tfm_kwargs = {'tfm_y': TfmY.Point}

from fastai.vision.data import get_annotations
from matplotlib import patches, patheffects

def _draw_outline(o, lw):
    o.set_path_effects([patheffects.Stroke(linewidth=lw, foreground='black'), patheffects.Normal()])

def _draw_rect(ax, b, color='white', text=None, text_size=14):
    patch = ax.add_patch(patches.Rectangle(b[:2], *b[-2:], fill=False, edgecolor=color, lw=2))
    _draw_outline(patch, 4)
    if text is not None:
        patch = ax.text(*b[:2], text, verticalalignment='top', color=color, fontsize=text_size, weight='bold')
        _draw_outline(patch,1)

class BBoxScaler(PointScaler):

    def __call__(self, o, tfm_y=TfmY.Bbox):
        (x,y) = o
        return x, (super().__call__((x,y[0]))[1].view(-1,4),y[1])
    def decode(self, o, tfm_y=TfmY.Bbox):
        (x,y) = o
        _,bbox = super().decode((x,y[0].view(-1,2)))
        return x, (bbox.view(-1,4),y[1])

class BBoxEncoder(Transform):
    _order=1
    def __init__(self): self.vocab = None
    def __call__(self,x): return (x[0],[self.otoi[o] for o in x[1] if o in self.otoi])
    def decode(self, o):  return (o[0], [self.vocab[i] for i in o[1]])

    def setup(self, items):
        if self.vocab is not None: return
        vals = set()
        for c in items.train: vals = vals.union(set(c[1]))
        self.vocab = uniqueify(list(vals), sort=True)
        self.vocab.insert(0, 'background')
        self.otoi  = {v:k for k,v in enumerate(self.vocab)}

    def show(self, x, ax):
        bbox,label = x
        for b,l in zip(bbox, label):
            if l != 'background': _draw_rect(ax, [b[1],b[0],b[3]-b[1],b[2]-b[0]], text=l)

class BBox(Item):
    default_tfm = BBoxEncoder
    default_tfm_ds = BBoxScaler
    default_tfm_kwargs = {'tfm_y': TfmY.Bbox}

def bb_pad_collate(samples, pad_idx=0):
    max_len = max([len(s[1][1]) for s in samples])
    bboxes = torch.zeros(len(samples), max_len, 4)
    labels = torch.zeros(len(samples), max_len).long() + pad_idx
    imgs = []
    for i,s in enumerate(samples):
        imgs.append(s[0][None])
        bbs, lbls = s[1]
        if not (bbs.nelement() == 0):
            bboxes[i,-len(lbls):] = bbs
            labels[i,-len(lbls):] = tensor(lbls)
    return torch.cat(imgs,0), (bboxes,labels)