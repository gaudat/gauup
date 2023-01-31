def rle_get(arr, offset, horizon):
    res = np.where(np.sum(arr[offset:][:horizon] == arr[offset], axis=-1) < arr.shape[1])[0]
    if res.shape == (0,):
        return arr[offset], horizon
    return arr[offset], np.min(res)

def rle_gen(arr, horizon):
    offset = 0
    while offset < arr.shape[0]:
        val, rl = rle_get(arr, offset, horizon)
        yield val, rl
        offset += rl

def rle_collapse(gen):
    val_old = None
    rl_old = 0
    for val, rl in gen:
        if val_old is not None and np.array_equal(val_old, val):
            rl_old += rl
        else:
            if val_old is not None:
                yield val_old, rl_old
            val_old = val
            rl_old = rl
    else:
        yield val_old, rl_old

