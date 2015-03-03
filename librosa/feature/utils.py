#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Feature manipulation utilities"""

import numpy as np
import scipy.signal

from .. import cache
from .. import util

__all__ = ['delta', 'stack_memory', 'sync', 'chroma_to_tonnetz']


@cache
def delta(data, width=9, order=1, axis=-1, trim=True):
    r'''Compute delta features: local estimate of the derivative
    of the input data along the selected axis.


    Parameters
    ----------
    data      : np.ndarray
        the input data matrix (eg, spectrogram)

    width     : int >= 3, odd [scalar]
        Number of frames over which to compute the delta feature

    order     : int > 0 [scalar]
        the order of the difference operator.
        1 for first derivative, 2 for second, etc.

    axis      : int [scalar]
        the axis along which to compute deltas.
        Default is -1 (columns).

    trim      : bool
        set to `True` to trim the output matrix to the original size.

    Returns
    -------
    delta_data   : np.ndarray [shape=(d, t) or (d, t + window)]
        delta matrix of `data`.

    Examples
    --------
    Compute MFCC deltas, delta-deltas

    >>> y, sr = librosa.load(librosa.util.example_audio_file())
    >>> mfcc = librosa.feature.mfcc(y=y, sr=sr)
    >>> mfcc_delta = librosa.feature.delta(mfcc)
    >>> mfcc_delta
    array([[ -4.250e+03,  -3.060e+03, ...,  -4.547e-13,  -4.547e-13],
           [  5.673e+02,   6.931e+02, ...,   0.000e+00,   0.000e+00],
    ...,
           [ -5.986e+01,  -5.018e+01, ...,   0.000e+00,   0.000e+00],
           [ -3.112e+01,  -2.908e+01, ...,   0.000e+00,   0.000e+00]])
    >>> mfcc_delta2 = librosa.feature.delta(mfcc, order=2)
    >>> mfcc_delta2
    array([[ -4.297e+04,  -3.207e+04, ...,  -8.185e-11,  -5.275e-11],
           [  5.736e+03,   5.420e+03, ...,  -7.390e-12,  -4.547e-12],
    ...,
           [ -6.053e+02,  -4.801e+02, ...,   0.000e+00,   0.000e+00],
           [ -3.146e+02,  -2.615e+02, ...,  -4.619e-13,  -2.842e-13]])

    >>> import matplotlib.pyplot as plt
    >>> plt.subplot(3, 1, 1)
    >>> librosa.display.specshow(mfcc)
    >>> plt.title('MFCC')
    >>> plt.colorbar()
    >>> plt.subplot(3, 1, 2)
    >>> librosa.display.specshow(mfcc_delta)
    >>> plt.title(r'MFCC-$\Delta$')
    >>> plt.colorbar()
    >>> plt.subplot(3, 1, 3)
    >>> librosa.display.specshow(mfcc_delta2, x_axis='time')
    >>> plt.title(r'MFCC-$\Delta^2$')
    >>> plt.colorbar()
    >>> plt.tight_layout()

    '''

    data = np.atleast_1d(data)

    if width < 3 or np.mod(width, 2) != 1:
        raise ValueError('width must be an odd integer >= 3')

    if order <= 0 or not isinstance(order, int):
        raise ValueError('order must be a positive integer')

    half_length = 1 + int(width // 2)
    window = np.arange(half_length - 1., -half_length, -1.)

    # Normalize the window so we're scale-invariant
    window /= np.sum(np.abs(window)**2)

    # Pad out the data by repeating the border values (delta=0)
    padding = [(0, 0)] * data.ndim
    padding[axis] = (width, width)
    delta_x = np.pad(data, padding, mode='edge')

    for _ in range(order):
        delta_x = scipy.signal.lfilter(window, 1, delta_x, axis=axis)

    # Cut back to the original shape of the input data
    if trim:
        idx = [Ellipsis] * delta_x.ndim
        idx[axis] = slice(- half_length - data.shape[axis], - half_length)
        delta_x = delta_x[idx]

    return delta_x


@cache
def stack_memory(data, n_steps=2, delay=1, **kwargs):
    """Short-term history embedding: vertically concatenate a data
    vector or matrix with delayed copies of itself.

    Each column `data[:, i]` is mapped to::

        data[:, i] ->  [data[:, i],
                        data[:, i - delay],
                        ...
                        data[:, i - (n_steps-1)*delay]]

    For columns `i < (n_steps - 1) * delay` , the data will be padded.
    By default, the data is padded with zeros, but this behavior can be
    overridden by supplying additional keyword arguments which are passed
    to `np.pad()`.


    Parameters
    ----------
    data : np.ndarray [shape=(t,) or (d, t)]
        Input data matrix.  If `data` is a vector (`data.ndim == 1`),
        it will be interpreted as a row matrix and reshaped to `(1, t)`.

    n_steps : int > 0 [scalar]
        embedding dimension, the number of steps back in time to stack

    delay : int > 0 [scalar]
        the number of columns to step

    kwargs : additional keyword arguments
      Additional arguments to pass to `np.pad`.

    Returns
    -------
    data_history : np.ndarray [shape=(m * d, t)]
        data augmented with lagged copies of itself,
        where `m == n_steps - 1`.

    Examples
    --------
    Keep two steps (current and previous)

    >>> data = np.arange(-3, 3)
    >>> librosa.feature.stack_memory(data)
    array([[-3, -2, -1,  0,  1,  2],
           [ 0, -3, -2, -1,  0,  1]])

    Or three steps

    >>> librosa.feature.stack_memory(data, n_steps=3)
    array([[-3, -2, -1,  0,  1,  2],
           [ 0, -3, -2, -1,  0,  1],
           [ 0,  0, -3, -2, -1,  0]])

    Use reflection padding instead of zero-padding

    >>> librosa.feature.stack_memory(data, n_steps=3, mode='reflect')
    array([[-3, -2, -1,  0,  1,  2],
           [-2, -3, -2, -1,  0,  1],
           [-1, -2, -3, -2, -1,  0]])

    Or pad with edge-values, and delay by 2

    >>> librosa.feature.stack_memory(data, n_steps=3, delay=2, mode='edge')
    array([[-3, -2, -1,  0,  1,  2],
           [-3, -3, -3, -2, -1,  0],
           [-3, -3, -3, -3, -3, -2]])

    Stack time-lagged beat-synchronous chroma edge padding

    >>> y, sr = librosa.load(librosa.util.example_audio_file())
    >>> chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    >>> tempo, beats = librosa.beat.beat_track(y=y, sr=sr, hop_length=512)
    >>> chroma_sync = librosa.feature.sync(chroma, beats)
    >>> chroma_lag = librosa.feature.stack_memory(chroma_sync, n_steps=3,
    ...                                           mode='edge')

    Plot the result

    >>> import matplotlib.pyplot as plt
    >>> librosa.display.specshow(chroma_lag, y_axis='chroma')
    >>> librosa.display.time_ticks(librosa.frames_to_time(beats, sr=sr))
    >>> plt.yticks([0, 12, 24], ['Lag=0', 'Lag=1', 'Lag=2'])
    >>> plt.title('Time-lagged chroma')
    >>> plt.colorbar()
    >>> plt.tight_layout()
    """

    if n_steps < 1:
        raise ValueError('n_steps must be a positive integer')

    if delay < 1:
        raise ValueError('delay must be a positive integer')

    data = np.atleast_2d(data)

    t = data.shape[1]
    kwargs.setdefault('mode', 'constant')

    if kwargs['mode'] == 'constant':
        kwargs.setdefault('constant_values', [0])

    # Pad the end with zeros, which will roll to the front below
    data = np.pad(data, [(0, 0), ((n_steps - 1) * delay, 0)], **kwargs)

    history = data

    for i in range(1, n_steps):
        history = np.vstack([np.roll(data, -i * delay, axis=1), history])

    # Trim to original width
    history = history[:, :t]

    # Make contiguous
    return np.ascontiguousarray(history.T).T


@cache
def sync(data, frames, aggregate=None, pad=True):
    """Synchronous aggregation of a feature matrix

    .. note::
        In order to ensure total coverage, boundary points may be added
        to `frames`.

        If synchronizing a feature matrix against beat tracker output, ensure
        that frame numbers are properly aligned and use the same hop length.

    Parameters
    ----------
    data      : np.ndarray [shape=(d, T) or shape=(T,)]
        matrix of features

    frames    : np.ndarray [shape=(m,)]
        ordered array of frame segment boundaries

    aggregate : function
        aggregation function (default: `np.mean`)

    pad : boolean
        If `True`, `frames` is padded to span the full range `[0, T]`

    Returns
    -------
    Y         : ndarray [shape=(d, M)]
        `Y[:, i] = aggregate(data[:, F[i-1]:F[i]], axis=1)`

    Raises
    ------
    ValueError
        If `data.ndim` is not 1 or 2

    Examples
    --------
    Beat-synchronous CQT spectra

    >>> y, sr = librosa.load(librosa.util.example_audio_file())
    >>> tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    >>> cqt = librosa.cqt(y=y, sr=sr)

    By default, use mean aggregation

    >>> cqt_avg = librosa.feature.sync(cqt, beats)

    Use median-aggregation instead of mean

    >>> cqt_med = librosa.feature.sync(cqt, beats,
    ...                                aggregate=np.median)

    Or sub-beat synchronization

    >>> sub_beats = librosa.segment.subsegment(cqt, beats)
    >>> cqt_med_sub = librosa.feature.sync(cqt, sub_beats, aggregate=np.median)

    Plot the results

    >>> import matplotlib.pyplot as plt
    >>> plt.figure()
    >>> plt.subplot(3, 1, 1)
    >>> librosa.display.specshow(librosa.logamplitude(cqt**2,
    ...                                               ref_power=np.max),
    ...                          x_axis='time')
    >>> plt.colorbar(format='%+2.0f dB')
    >>> plt.title('CQT power, shape={:s}'.format(cqt.shape))
    >>> plt.subplot(3, 1, 2)
    >>> librosa.display.specshow(librosa.logamplitude(cqt_med**2,
    ...                                               ref_power=np.max))
    >>> plt.colorbar(format='%+2.0f dB')
    >>> plt.title('Beat synchronous CQT power, '
    ...           'shape={:s}'.format(cqt_med.shape))
    >>> plt.subplot(3, 1, 3)
    >>> librosa.display.specshow(librosa.logamplitude(cqt_med_sub**2,
    ...                                               ref_power=np.max))
    >>> plt.colorbar(format='%+2.0f dB')
    >>> plt.title('Sub-beat synchronous CQT power, '
    ...           'shape={:s}'.format(cqt_med_sub.shape))
    >>> plt.tight_layout()

    """

    if data.ndim > 2:
        raise ValueError('Synchronized data has ndim={:d},'
                         ' must be 1 or 2.'.format(data.ndim))

    data = np.atleast_2d(data)

    if aggregate is None:
        aggregate = np.mean

    dimension, n_frames = data.shape

    frames = util.fix_frames(frames, 0, n_frames, pad=pad)

    data_agg = np.empty((dimension, len(frames)-1), order='F')

    start = frames[0]

    for (i, end) in enumerate(frames[1:]):
        data_agg[:, i] = aggregate(data[:, start:end], axis=1)
        start = end

    return data_agg


@cache
def chroma_to_tonnetz(chromagram, norm=np.inf):
    '''Computes the tonal centroid features (tonnetz) from a 12-dimensional
    chromagram.

    Parameters
    ----------
    chromagram : np.ndarray [shape=(12, t)]
        Normalized energy for each chroma bin at each frame.

    norm : float or None
        Column-wise normalization.
        See `librosa.util.normalize` for details.

        If `None`, no normalization is performed.

    Returns
    -------
    tonnetz : np.ndarray [shape(6, t)]
        Tonal centroid features for each frame.

    See Also
    --------
    librosa.feature.chroma_cqt
        Compute a chromagram from a constat-Q transform.
    librosa.feature.chroma_stft
        Compute a chromagram from an STFT spectrogram or waveform.

    Examples
    --------
    >>> y, sr = librosa.load(librosa.util.example_audio_file())
    >>> chroma = librosa.feature.chroma_stft(y=y, sr=sr)
    >>> tonnetz = librosa.feature.chroma_to_tonnetz(chroma)
    >>> tonnetz
    array([[ 0.79506535,  0.17179337,  0.30261799, ...,  0.05586615,
         0.14303219,  0.187812  ],
       [-0.44264622,  0.41896667,  0.21596437, ...,  0.11552605,
         0.13349843,  0.92497935],
       [-1.        ,  0.46310843, -1.        , ...,  0.4240766 ,
         0.62088668,  0.74145399],
       [ 0.50550166, -1.        ,  0.33409652, ..., -1.        ,
        -1.        , -1.        ],
       [-0.34921771,  0.52859071, -0.14055977, ...,  0.05132072,
        -0.05028974, -0.22788206],
       [-0.01232449, -0.19507053, -0.07335521, ..., -0.43501825,
        -0.49050545, -0.36520804]])

    >>> import matplotlib.pyplot as plt
    >>> librosa.display.specshow(tonnetz, x_axis='time')
    >>> plt.colorbar()
    >>> plt.title('Tonal Centroids (Tonnetz)')
    >>> plt.tight_layout()
    '''

    if chromagram.shape[0] != 12:
        raise ValueError('Tonnetz can only be obtained from 12-dimensional '
                         'chromagrams.')

    t = chromagram.shape[1]
    tonnetz = np.zeros((6, t))

    r1 = 1      # Fifths
    r2 = 1      # Minor
    r3 = 0.5    # Major

    # Generate Transformation matrix
    phi = np.zeros((6, 12))
    for i in range(6):
        for j in range(12):
            fun = np.sin if i % 2 == 0 else np.cos

            if i < 2:
                phi[i, j] = r1 * fun(j * 7 * np.pi / 6.)
            elif i >= 2 and i < 4:
                phi[i, j] = r2 * fun(j * 3 * np.pi / 2.)
            else:
                phi[i, j] = r3 * fun(j * 2 * np.pi / 3.)

    # Do the transform to tonnetz
    for i in range(t):
        denom = float(chromagram[:, i].sum())
        for d in range(6):
            if denom == 0:
                tonnetz[d, i] = 0
            else:
                tonnetz[d, i] = 1 / denom * (phi[d, :] * chromagram[:, i]).sum()

    return util.normalize(tonnetz, norm=norm, axis=0)
