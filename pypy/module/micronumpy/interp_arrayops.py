
from pypy.module.micronumpy.support import convert_to_array
from pypy.module.micronumpy import loop

def where(space, w_arr, w_x, w_y):
    """where(condition, [x, y])

    Return elements, either from `x` or `y`, depending on `condition`.

    If only `condition` is given, return ``condition.nonzero()``.

    Parameters
    ----------
    condition : array_like, bool
        When True, yield `x`, otherwise yield `y`.
    x, y : array_like, optional
        Values from which to choose. `x` and `y` need to have the same
        shape as `condition`.

    Returns
    -------
    out : ndarray or tuple of ndarrays
        If both `x` and `y` are specified, the output array contains
        elements of `x` where `condition` is True, and elements from
        `y` elsewhere.

        If only `condition` is given, return the tuple
        ``condition.nonzero()``, the indices where `condition` is True.

    See Also
    --------
    nonzero, choose

    Notes
    -----
    If `x` and `y` are given and input arrays are 1-D, `where` is
    equivalent to::

        [xv if c else yv for (c,xv,yv) in zip(condition,x,y)]

    Examples
    --------
    >>> np.where([[True, False], [True, True]],
    ...          [[1, 2], [3, 4]],
    ...          [[9, 8], [7, 6]])
    array([[1, 8],
           [3, 4]])

    >>> np.where([[0, 1], [1, 0]])
    (array([0, 1]), array([1, 0]))

    >>> x = np.arange(9.).reshape(3, 3)
    >>> np.where( x > 5 )
    (array([2, 2, 2]), array([0, 1, 2]))
    >>> x[np.where( x > 3.0 )]               # Note: result is 1D.
    array([ 4.,  5.,  6.,  7.,  8.])
    >>> np.where(x < 5, x, -1)               # Note: broadcasting.
    array([[ 0.,  1.,  2.],
           [ 3.,  4., -1.],
           [-1., -1., -1.]])

    
    NOTE: support for not passing x and y is unsupported
    """
    arr = convert_to_array(space, w_arr)
    x = convert_to_array(space, w_x)
    y = convert_to_array(space, w_y)
    return loop.where(space, arr, x, y)
