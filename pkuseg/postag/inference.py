# distutils: language = c++
# cython: infer_types=True
# cython: language_level=3
import numpy as np


# np.import_array()


class belief:
    def __init__(self, nNodes, nStates):
        self.belState = np.zeros((nNodes, nStates))
        self.belEdge = np.zeros((nNodes, nStates * nStates))
        self.Z = 0


def get_beliefs(bel, m, x, Y, YY):
    belState = bel.belState
    belEdge = bel.belEdge
    nNodes = len(x)
    nTag = m.n_tag
    Z = 0
    alpha_Y = np.zeros(nTag)
    newAlpha_Y = np.zeros(nTag)
    tmp_Y = np.zeros(nTag)
    YY_trans = YY.transpose()
    YY_t_r = YY_trans.reshape(-1)
    sum_edge = np.zeros(nTag * nTag)

    for i in range(nNodes - 1, 0, -1):
        tmp_Y = belState[i] + Y[i]
        belState[i-1] = logMultiply(YY, tmp_Y)

    for i in range(nNodes):
        if i > 0:
            tmp_Y = alpha_Y.copy()
            newAlpha_Y = logMultiply(YY_trans, tmp_Y) + Y[i]
        else:
            newAlpha_Y = Y[i].copy()
        if i > 0:
            tmp_Y = Y[i] + belState[i]
            belEdge[i] = YY_t_r
            for yPre in range(nTag):
                for y in range(nTag):
                    belEdge[i, y * nTag + yPre] += tmp_Y[y] + alpha_Y[yPre]
        belState[i] = belState[i] + newAlpha_Y
        alpha_Y = newAlpha_Y

    Z = logSum(alpha_Y)
    for i in range(nNodes):
        belState[i] = np.exp(belState[i] - Z)
    for i in range(1, nNodes):
        sum_edge += np.exp(belEdge[i] - Z)

    return Z, sum_edge


def run_viterbi(node_score, edge_score):
    i, y, y_pre, i_pre, tag = 0, 0, 0, 0, 0
    w = node_score.shape[0]
    h = node_score.shape[1]
    ma, sc = 0.0, 0.0
    max_score = np.zeros((w, h), dtype=np.float64)
    pre_tag = np.zeros((w, h), dtype=np.int32)
    init_check = np.zeros((w, h), dtype=np.uint8)
    states = np.zeros(w, dtype=np.int32)

    for y in range(h):
        max_score[w-1, y] = node_score[w-1, y]

    for i in range(w - 2, -1, -1):
        for y in range(h):
            for y_pre in range(h):
                i_pre = i + 1
                sc = max_score[i_pre, y_pre] + node_score[i, y] + edge_score[y, y_pre]
                if not init_check[i, y]:
                    # 判断是否是起始第一次赋值
                    init_check[i, y] = 1
                    max_score[i, y] = sc
                    pre_tag[i, y] = y_pre
                elif sc >= max_score[i, y]:
                    # 用大值将小值覆盖
                    max_score[i, y] = sc
                    pre_tag[i, y] = y_pre

    ma = max_score[0, 0]
    tag = 0
    for y in range(1, h):
        sc = max_score[0, y]
        if ma < sc:
            ma = sc
            tag = y

    states[0] = tag
    for i in range(1, w):
        tag = pre_tag[i-1, tag]
        states[i] = tag

    if ma > 300:
        ma = 300

    return np.exp(ma), states


def getLogYY(feature_temp, num_tag, backoff, w, scalar):
    num_node = len(feature_temp)  # feature_temp.size()
    node_score = np.zeros((num_node, num_tag), dtype=np.float64)
    edge_score = np.ones((num_tag, num_tag), dtype=np.float64)
    s, s_pre, i = 0, 0, 0
    maskValue, tmp = 0.0, 0.0
    f_list = list()
    f, ft = 0, 0

    for i in range(num_node):
        f_list = feature_temp[i]
        for ft in f_list:
            for s in range(num_tag):
                f = ft * num_tag + s
                node_score[i, s] += w[f] * scalar
    for s in range(num_tag):
        for s_pre in range(num_tag):
            f = backoff + s * num_tag + s_pre
            edge_score[s_pre, s] += w[f] * scalar

    return node_score, edge_score


def maskY(tags, nNodes, nTag, Y):
    mask_Yi = Y.copy()
    maskValue = -1e100
    tagList = tags
    i = 0
    for i in range(nNodes):
        for s in range(nTag):
            if tagList[i] != s:
                mask_Yi[i, s] = maskValue
    return mask_Yi


def logMultiply(A, B):
    r, c = 0, 0
    toSumLists = np.zeros_like(A)
    ret = np.zeros(A.shape[0])

    for r in range(A.shape[0]):
        for c in range(A.shape[1]):
            toSumLists[r, c] = A[r, c] + B[c]
    for r in range(A.shape[0]):
        ret[r] = logSum(toSumLists[r])

    return ret


def logSum(a):
    n = a.shape[0]
    s = a[0]
    m1, m2 = 0.0, 0.0
    for i in range(1, n):
        if s >= a[i]:
            m1, m2 = s, a[i]
        else:
            m1, m2 = a[i], s
        s = m1 + np.log(1 + np.exp(m2 - m1))

    return s


def decodeViterbi_fast(feature_temp, model):
    Y, YY = getLogYY(feature_temp, model.n_tag, model.n_feature*model.n_tag, model.w, 1.0)
    numer, tags = run_viterbi(Y, YY)
    tags = list(tags)
    return numer, tags


def getYYandY(model, example):
    Y, YY = getLogYY(example.features, model.n_tag, model.n_feature*model.n_tag, model.w, 1.0)
    mask_Y = maskY(example.tags, len(example), model.n_tag, Y)
    mask_YY = YY
    return Y, YY, mask_Y, mask_YY

