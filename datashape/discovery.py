from __future__ import print_function, division, absolute_import

import numpy as np
from dateutil.parser import parse as dateparse
from datetime import datetime, date, time
from .dispatch import dispatch
from time import strptime

from .coretypes import (int32, int64, float64, bool_, complex128, datetime_,
                        Option, isdimension, var, from_numpy, Tuple, null,
                        Record, string, Null, DataShape, real, date_, time_,
                        Mono)
from .py2help import _strtypes, _inttypes
from .internal_utils import _toposort, groupby


__all__ = ['discover']


@dispatch(_inttypes)
def discover(i):
    return int64


@dispatch(float)
def discover(f):
    return float64


@dispatch(bool)
def discover(b):
    return bool_


@dispatch(complex)
def discover(z):
    return complex128


@dispatch(datetime)
def discover(dt):
    if dt.time() and dt.date():
        return datetime_
    elif dt.date():
        return date_
    else:
        return time_


@dispatch(date)
def discover(dt):
    return date_


@dispatch(time)
def discover(t):
    return time_


@dispatch((type(None), Null))
def discover(i):
    return null


bools = {'False': False,
         'false': False,
         'True': True,
         'true': True}


string_coercions = [int, float, bools.__getitem__, dateparse]


@dispatch(_strtypes)
def discover(s):
    if not s:
        return null
    for f in string_coercions:
        try:
            return discover(f(s))
        except:
            pass

    return string


@dispatch((tuple, list))
def discover(seq):
    unite = do_one([unite_identical, unite_base, unite_merge_dimensions])
    # [(a, b), (a, c)]
    if (all(isinstance(item, (tuple, list)) for item in seq) and
            len(set(map(len, seq))) == 1):
        columns = list(zip(*seq))
        try:
            types = [unite([discover(dshape) for dshape in column]).subshape[0]
                                             for column in columns]
            unite = do_one([unite_identical, unite_merge_dimensions, Tuple])
            return len(seq) * unite(types)
        except AttributeError: # no subshape available
            pass
    # [{k: v, k: v}, {k: v, k: v}]
    if (all(isinstance(item, dict) for item in seq) and
            len(set(frozenset(item.keys()) for item in seq)) == 1):
        keys = sorted(seq[0].keys())
        columns = [[item[key] for item in seq] for key in keys]
        try:
            types = [unite([discover(dshape) for dshape in column]).subshape[0]
                                             for column in columns]
            return len(seq) * Record(list(zip(keys, types)))
        except AttributeError:
            pass


    types = list(map(discover, seq))
    return do_one([unite_identical, unite_merge_dimensions, Tuple])(types)


def isnull(ds):
    return ds == null or ds == DataShape(null)


identity = lambda x: x

# (a, b) implies that b can turn into a
edges = [
         (string, int64),  # E.g. int64 can be turned into a string
         (string, real),
         (string, date_),
         (string, datetime_),
         (string, bool_),
         (datetime_, date_),
         (string, datetime_),
         (int64, int32),
         (real, int64),
         (string, null)]

numeric_edges = [
         (int64, int32),
         (real, int64),
         (string, null)
         ]


# {a: [b, c]} a is more general than b or c
edges = groupby(lambda x: x[1], edges)
edges = dict((k, set(a for a, b in v)) for k, v in edges.items())
toposorted = _toposort(edges)


def lowest_common_dshape(dshapes):
    """ Find common shared dshape

    >>> lowest_common_dshape([int32, int64, float64])
    ctype("float64")

    >>> lowest_common_dshape([int32, int64])
    ctype("int64")

    >>> lowest_common_dshape([string, int64])
    ctype("string")
    """
    common = set.intersection(*[descendents(edges, ds) for ds in dshapes])
    if common:
        return min(common, key=toposorted.index)


def unite_base(dshapes):
    """ Performs lowest common dshape and also null aware

    >>> unite_base([float64, float64, int64])
    dshape("3 * float64")

    >>> unite_base([int32, int64, null])
    dshape("3 * ?int64")
    """
    dshapes = [unpack(ds) for ds in dshapes]
    bynull = groupby(isnull, dshapes)
    base = lowest_common_dshape(bynull.get(False, []))
    if base:
        if bynull.get(True):
            base = Option(base)
        return len(dshapes) * base


def unite_identical(dshapes):
    """

    >>> unite_identical([int32, int32, int32])
    dshape("3 * int32")
    """
    if len(set(dshapes)) == 1:
        return len(dshapes) * dshapes[0]



def unite_merge_dimensions(dshapes, unite=unite_identical):
    """

    >>> unite_merge_dimensions([10 * string, 10 * string])
    dshape("2 * 10 * string")

    >>> unite_merge_dimensions([10 * string, 20 * string])
    dshape("2 * var * string")
    """
    n = len(dshapes)
    if all(isinstance(ds, DataShape) and isdimension(ds[0]) for ds in dshapes):
        dims = [ds[0] for ds in dshapes]
        base = unite([ds.subshape[0] for ds in dshapes])
        if base:
            if len(set(dims)) == 1:
                return n * (dims[0] * base.subshape[0])
            else:
                return n * (var * base.subshape[0])


def do_one(funcs):
    def f(inp):
        for func in funcs:
            result = func(inp)
            if result:
                return result
        return inp
    return f


def unpack(ds):
    """ Unpack DataShape constructor if unnecessary

    Record packs inputs in DataShape containers.  This unpacks it.

    >>> from datashape import dshape
    >>> unpack(dshape('string'))
    ctype("string")
    """
    if isinstance(ds, DataShape) and len(ds) == 1:
        return ds[0]
    else:
        return ds


@dispatch(dict)
def discover(d):
    return Record([[k, discover(d[k])] for k in sorted(d)])


@dispatch(np.number)
def discover(n):
    return from_numpy((), type(n))


@dispatch(np.ndarray)
def discover(X):
    return from_numpy(X.shape, X.dtype)


def descendents(d, x):
    """

    >>> d = {3: [2], 2: [1, 0], 5: [6]}
    >>> sorted(descendents(d, 3))
    [0, 1, 2, 3]
    """
    desc = set([x])
    children = d.get(x, set())
    while children:
        children = set.union(*[set(d.get(kid, ())) for kid in desc])
        children -= desc
        desc.update(children)
    return desc
