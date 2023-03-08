#include "cwsPrediction.h"

ConstLabels *newConstLabels(){
    ConstLabels *constLabelsObj = NULL;
    constLabelsObj = (ConstLabels *)malloc(sizeof(ConstLabels));

    constLabelsObj->startFeature = L"[START]";
    constLabelsObj->endFeature = L"[END]";
    constLabelsObj->delim = L".";

    // 字符以 c 为中心，前后，z、a、b、c、d、e、f 依次扩展开
    constLabelsObj->charCurrent = L"c";
    constLabelsObj->charBefore = L"b";          // c-1.
    constLabelsObj->charNext = L"d";            // c1.
    constLabelsObj->charBefore2 = L"a";         // c-2.
    constLabelsObj->charNext2 = L"e";           // c2.
    constLabelsObj->charBefore3 = L"z";         // c-3.
    constLabelsObj->charNext3 = L"f";           // c3.
    constLabelsObj->charBeforeCurrent = L"bc";  // c-1c.
    constLabelsObj->charBefore2Current = L"ac"; // c-2c.
    constLabelsObj->charBefore3Current = L"zc"; // c-3c.
    constLabelsObj->charCurrentNext = L"cd";    // cc1.
    constLabelsObj->charCurrentNext2 = L"ce";   // cc2.
    constLabelsObj->charCurrentNext3 = L"cf";   // cc3.
    // const wchar_t *charBefore21 = L"ab";       // c-2c-1.
    // const wchar_t *charNext12 = L"de";         // c1c2.

    constLabelsObj->wordBefore = L"v";  // w-1.
    constLabelsObj->wordNext = L"x";    // w1.
    constLabelsObj->word2Left = L"wl";  // ww.l.
    constLabelsObj->word2Right = L"wr"; // ww.r.

    constLabelsObj->wordMax = 4;
    constLabelsObj->wordMin = 2;
    constLabelsObj->wordLength = L"234";
}

CwsPrediction *newCwsPrediction()
{
    // initialize
    CwsPrediction *cwsPredictionObj = NULL;
    cwsPredictionObj = (CwsPrediction *)malloc(sizeof(CwsPrediction));
    if (cwsPredictionObj == NULL) {
        return NULL;
    }

    cwsPredictionObj->unigramSetHashTableItemSize = 0;
    cwsPredictionObj->unigramSetHashTableMaxSize = 0;

    cwsPredictionObj->bigramSetHashTableItemSize = 0;
    cwsPredictionObj->bigramSetHashTableMaxSize = 0;

    cwsPredictionObj->featureToIdxDictHashTableItemSize = 0;
    cwsPredictionObj->featureToIdxDictHashTableMaxSize = 0;

    ConstLabels *constLabelsObj = newConstLabels();
    cwsPredictionObj->constLabels = constLabelsObj;

    // link functions
    cwsPredictionObj->_Init = Init;
    cwsPredictionObj->_Cut = Cut;

    return cwsPredictionObj;
}

int Init(
    CwsPrediction *cwsPredictionObj,
    int unigramSetHashTableMaxSize,
    const char *unigramFilePath,
    int bigramSetHashTableMaxSize,
    const char *bigramFilePath,
    int featureToIdxDictHashTableMaxSize,
    const char *featureToIdxFilePath)
{
    cwsPredictionObj->unigramSetHashTableMaxSize = unigramSetHashTableMaxSize;

    cwsPredictionObj->UnigramSetHashTable = (SetHashNode **)malloc(sizeof(SetHashNode) * unigramSetHashTableMaxSize);
    memset(cwsPredictionObj->UnigramSetHashTable, 0,
        sizeof(SetHashNode *) * unigramSetHashTableMaxSize);

    cwsPredictionObj->bigramSetHashTableMaxSize = bigramSetHashTableMaxSize;

    cwsPredictionObj->BigramSetHashTable = (SetHashNode **)malloc(sizeof(SetHashNode) * unigramSetHashTableMaxSize);
    memset(cwsPredictionObj->BigramSetHashTable, 0,
           sizeof(SetHashNode *) * bigramSetHashTableMaxSize);

    cwsPredictionObj->featureToIdxDictHashTableMaxSize = featureToIdxDictHashTableMaxSize;

    cwsPredictionObj->featureToIdxDictHashTable = (DictHashNode **)malloc(sizeof(DictHashNode) * featureToIdxDictHashTableMaxSize);
    memset(cwsPredictionObj->featureToIdxDictHashTable, 0,
           sizeof(SetHashNode *) * featureToIdxDictHashTableMaxSize);

    // read file and build unigram_set_hash_table
    clock_t start, end;
    wchar_t buff[30];
    FILE *fp = NULL;
    start = clock();
    fp = fopen(unigramFilePath, "r");
    while (fgetws(buff, 30, (FILE *)fp))
    {
        int lens = wcslen(buff);
        buff[lens - 1] = L'\0';

        set_hash_table_insert(
            cwsPredictionObj->UnigramSetHashTable,
            buff,
            cwsPredictionObj->unigramSetHashTableMaxSize);
        // printf("=>: %ls, %d\n", buff, wcslen(buff));
        cwsPredictionObj->unigramSetHashTableItemSize++;
    }
    fclose(fp);
    end = clock();
    printf("build unigram hash table   time=%f\n", (double)(end - start) / CLOCKS_PER_SEC);
    distribution_statistics(cwsPredictionObj->UnigramSetHashTable,
                            cwsPredictionObj->unigramSetHashTableMaxSize,
                            cwsPredictionObj->unigramSetHashTableItemSize);

    // read file and build bigram_set_hash_table
    fp = NULL;
    start = clock();
    fp = fopen(bigramFilePath, "r");
    while (fgetws(buff, 30, (FILE *)fp))
    {
        int lens = wcslen(buff);
        buff[lens - 1] = L'\0';

        set_hash_table_insert(
            cwsPredictionObj->BigramSetHashTable,
            buff,
            cwsPredictionObj->bigramSetHashTableMaxSize);
        // printf("=>: %ls, %d\n", buff, wcslen(buff));
        cwsPredictionObj->bigramSetHashTableItemSize++;
    }
    fclose(fp);
    end = clock();
    printf("build bigram hash table    time=%f\n", (double)(end - start) / CLOCKS_PER_SEC);
    distribution_statistics(cwsPredictionObj->BigramSetHashTable,
                            cwsPredictionObj->bigramSetHashTableMaxSize,
                            cwsPredictionObj->bigramSetHashTableItemSize);

    // read file and build feature_to_idx_dict_hash_table
    fp = NULL;
    start = clock();
    fp = fopen(featureToIdxFilePath, "r");
    while (fgetws(buff, 30, (FILE *)fp))
    {
        int lens = wcslen(buff);
        buff[lens - 1] = L'\0';

        dict_hash_table_insert(
            cwsPredictionObj->featureToIdxDictHashTable,
            buff,
            cwsPredictionObj->featureToIdxDictHashTableItemSize,
            cwsPredictionObj->featureToIdxDictHashTableMaxSize);
        // printf("=>: %ls, %d\n", buff, wcslen(buff));
        cwsPredictionObj->featureToIdxDictHashTableItemSize++;
    }
    fclose(fp);
    end = clock();
    printf("build feature_to_idx hash table    time=%f\n", (double)(end - start) / CLOCKS_PER_SEC);
    dict_distribution_statistics(cwsPredictionObj->featureToIdxDictHashTable,
                                 cwsPredictionObj->featureToIdxDictHashTableMaxSize,
                                 cwsPredictionObj->featureToIdxDictHashTableItemSize);
    return 1;
}

PyObject *Cut(CwsPrediction *cwsPredictionObj, wchar_t *text)
{
    PyObject *featureList = PyList_New(0);
    int textLength = wcslen(text);
    int ret;

    for (int i = 0; i < textLength; i++)
    {
        wchar_t **featureObj = getCwsNodeFeature(
            cwsPredictionObj, i, text, textLength);
        PyObject *featureIdxList = getFeatureIndex(
            cwsPredictionObj, featureObj);
        ret = PyList_Size(featureIdxList);
        printf("idx len: %d\n", ret);

        // release memory
        while(*featureObj) {
            free(*featureObj);
            featureObj = featureObj + 1;
        }

        ret = PyList_Append(featureList, featureIdxList);
    }

    return featureList;
}

wchar_t *getSliceStr(wchar_t *text, int start, int length, int all_len, wchar_t *emptyStr)
{
    if (start < 0 || start >= all_len)
    {
        return emptyStr;
    }
    if (start + length > all_len)
    {
        return emptyStr;
    }

    // 返回相应的子字符串
    wchar_t *resStr = malloc((length + 1) * sizeof(wchar_t));
    wcsncpy(resStr, text + start, length);
    wcsncpy(resStr + length, emptyStr, 1);
    // printf("the length of slice: %ld. %ls\n\n", wcslen(resStr), resStr);
    return resStr;
}

wchar_t **getCwsNodeFeature(CwsPrediction *cwsPredictionObj,
                            int idx, wchar_t *text, int nodeNum)
{
    wchar_t *emptyStr = malloc(sizeof(wchar_t));
    memset(emptyStr, L'\0', sizeof(wchar_t));

    int ret = -1;
    wchar_t *curC = text + idx;        // 当前字符
    wchar_t *beforeC = text + idx - 1; // 前一个字符
    wchar_t *nextC = text + idx + 1;   // 后一个字符

    int featureIdx = 0;
    wchar_t **featureList = (wchar_t **)malloc(20 * sizeof(wchar_t *));
    memset(featureList, 0, sizeof(wchar_t *) * 20);

    // setlocale(LC_ALL, "en_US.UTF-8");

    // 添加当前字特征
    wchar_t *charCurrentFeature = malloc(3 * sizeof(wchar_t)); // 默认为 2，如 “c佛”
    wcsncpy(charCurrentFeature, cwsPredictionObj->constLabels->charCurrent, 1);
    wcsncpy(charCurrentFeature + 1, curC, 1);
    wcsncpy(charCurrentFeature + 2, emptyStr, 1);
    *(featureList + featureIdx) = charCurrentFeature;
    featureIdx++;

    if (idx > 0)
    {
        // 添加前一字特征
        wchar_t *charBeforeFeature = malloc(3 * sizeof(wchar_t)); // 默认为 2，如 “b租”
        wcsncpy(charBeforeFeature, cwsPredictionObj->constLabels->charBefore, 1);
        wcsncpy(charBeforeFeature + 1, beforeC, 1);
        wcsncpy(charBeforeFeature + 2, emptyStr, 1);
        *(featureList + featureIdx) = charBeforeFeature;
        featureIdx++;

        // 添加当前字和前一字特征
        wchar_t *charBeforeCurrentFeature = malloc(6 * sizeof(wchar_t)); // 默认为 5，如 “bc佛.祖”
        wcsncpy(charBeforeCurrentFeature, cwsPredictionObj->constLabels->charBeforeCurrent, 2);
        wcsncpy(charBeforeCurrentFeature + 2, beforeC, 1);
        wcsncpy(charBeforeCurrentFeature + 3, cwsPredictionObj->constLabels->delim, 1);
        wcsncpy(charBeforeCurrentFeature + 4, curC, 1);
        wcsncpy(charBeforeCurrentFeature + 5, emptyStr, 1);

        *(featureList + featureIdx) = charBeforeCurrentFeature;
        featureIdx++;
    }
    else
    {
        // 添加起始位特征
        wchar_t *startFeature = malloc(8 * sizeof(wchar_t)); // 默认为 2，如 “b租”
        wcsncpy(startFeature, cwsPredictionObj->constLabels->startFeature, 8);
        *(featureList + featureIdx) = startFeature;
        featureIdx++;
    }

    if (idx < nodeNum - 1)
    {
        // 添加后一字特征
        wchar_t *charNextFeature = malloc(3 * sizeof(wchar_t)); // 默认为 2，如 “d租”
        wcsncpy(charNextFeature, cwsPredictionObj->constLabels->charNext, 1);
        wcsncpy(charNextFeature + 1, nextC, 1);
        wcsncpy(charNextFeature + 2, emptyStr, 1);
        *(featureList + featureIdx) = charNextFeature;
        featureIdx++;

        // 添加当前字和后一字特征
        wchar_t *charCurrentNextFeature = malloc(6 * sizeof(wchar_t)); // 默认为 2，如 “cd佛.祖”
        wcsncpy(charCurrentNextFeature, cwsPredictionObj->constLabels->charCurrentNext, 2);
        wcsncpy(charCurrentNextFeature + 2, curC, 1);
        wcsncpy(charCurrentNextFeature + 3, cwsPredictionObj->constLabels->delim, 1);
        wcsncpy(charCurrentNextFeature + 4, nextC, 1);
        wcsncpy(charCurrentNextFeature + 5, emptyStr, 1);
        *(featureList + featureIdx) = charCurrentNextFeature;
        featureIdx++;
    }
    else
    {
        // 添加文本终止符特征
        wchar_t *endFeature = malloc(6 * sizeof(wchar_t));
        wcsncpy(endFeature, cwsPredictionObj->constLabels->endFeature, 6);
        *(featureList + featureIdx) = endFeature;
        featureIdx++;
    }

    if (idx > 1)
    {
        wchar_t *beforeC2 = text + idx - 2;

        // 添加前第二字特征
        wchar_t *charBeforeC2Feature = malloc(3 * sizeof(wchar_t)); // 默认为 2，如 “a租”
        wcsncpy(charBeforeC2Feature, cwsPredictionObj->constLabels->charBefore2, 1);
        wcsncpy(charBeforeC2Feature + 1, beforeC2, 1);
        wcsncpy(charBeforeC2Feature + 2, emptyStr, 1);
        *(featureList + featureIdx) = charBeforeC2Feature;
        featureIdx++;

        // 添加前第二字和当前字组合特征
        wchar_t *charBefore2CurrentFeature = malloc(6 * sizeof(wchar_t)); // 默认为 5，如 “sc佛.在”
        wcsncpy(charBefore2CurrentFeature, cwsPredictionObj->constLabels->charBefore2Current, 2);
        wcsncpy(charBefore2CurrentFeature + 2, beforeC2, 1);
        wcsncpy(charBefore2CurrentFeature + 3, cwsPredictionObj->constLabels->delim, 1);
        wcsncpy(charBefore2CurrentFeature + 4, curC, 1);
        wcsncpy(charBefore2CurrentFeature + 5, emptyStr, 1);
        *(featureList + featureIdx) = charBefore2CurrentFeature;
        featureIdx++;
    }

    if (idx < nodeNum - 2)
    {
        wchar_t *nextC2 = text + idx + 2;

        // 添加后第二字特征
        wchar_t *charNextC2Feature = malloc(3 * sizeof(wchar_t)); // 默认为 2，如 “e租”
        wcsncpy(charNextC2Feature, cwsPredictionObj->constLabels->charNext2, 1);
        wcsncpy(charNextC2Feature + 1, nextC2, 1);
        wcsncpy(charNextC2Feature + 2, emptyStr, 1);
        *(featureList + featureIdx) = charNextC2Feature;
        featureIdx++;

        // 添加当前字和后第二字组合特征
        wchar_t *charCurrentNext2Feature = malloc(6 * sizeof(wchar_t)); // 默认为 5，如 “ce大.寺”
        wcsncpy(charCurrentNext2Feature, cwsPredictionObj->constLabels->charCurrentNext2, 2);
        wcsncpy(charCurrentNext2Feature + 2, curC, 1);
        wcsncpy(charCurrentNext2Feature + 3, cwsPredictionObj->constLabels->delim, 1);
        wcsncpy(charCurrentNext2Feature + 4, nextC2, 1);
        wcsncpy(charCurrentNext2Feature + 5, emptyStr, 1);
        *(featureList + featureIdx) = charCurrentNext2Feature;
        featureIdx++;
    }

    if (idx > 2)
    {
        wchar_t *beforeC3 = text + idx - 3;

        // 添加前第三字特征
        wchar_t *charBeforeC3Feature = malloc(3 * sizeof(wchar_t)); // 默认为 2，如 “z租”
        wcsncpy(charBeforeC3Feature, cwsPredictionObj->constLabels->charBefore3, 1);
        wcsncpy(charBeforeC3Feature + 1, beforeC3, 1);
        wcsncpy(charBeforeC3Feature + 2, emptyStr, 1);
        *(featureList + featureIdx) = charBeforeC3Feature;
        featureIdx++;

        // 添加前第三字和当前字组合特征
        wchar_t *charBefore3CurrentFeature = malloc(6 * sizeof(wchar_t)); // 默认为 5，如 “zc佛.在”
        wcsncpy(charBefore3CurrentFeature, cwsPredictionObj->constLabels->charBefore3Current, 2);
        wcsncpy(charBefore3CurrentFeature + 2, beforeC3, 1);
        wcsncpy(charBefore3CurrentFeature + 3, cwsPredictionObj->constLabels->delim, 1);
        wcsncpy(charBefore3CurrentFeature + 4, curC, 1);
        wcsncpy(charBefore3CurrentFeature + 5, emptyStr, 1);
        *(featureList + featureIdx) = charBefore3CurrentFeature;
        featureIdx++;
    }

    if (idx < nodeNum - 3)
    {
        wchar_t *nextC3 = text + idx + 3;

        // 添加后第三字特征
        wchar_t *charNextC3Feature = malloc(3 * sizeof(wchar_t)); // 默认为 2，如 “f租”
        wcsncpy(charNextC3Feature, cwsPredictionObj->constLabels->charNext3, 1);
        wcsncpy(charNextC3Feature + 1, nextC3, 1);
        wcsncpy(charNextC3Feature + 2, emptyStr, 1);
        *(featureList + featureIdx) = charNextC3Feature;
        featureIdx++;

        // 添加当前字和后第二字组合特征
        wchar_t *charCurrentNext3Feature = malloc(6 * sizeof(wchar_t)); // 默认为 5，如 “cf大.寺”
        wcsncpy(charCurrentNext3Feature, cwsPredictionObj->constLabels->charCurrentNext3, 2);
        wcsncpy(charCurrentNext3Feature + 2, curC, 1);
        wcsncpy(charCurrentNext3Feature + 3, cwsPredictionObj->constLabels->delim, 1);
        wcsncpy(charCurrentNext3Feature + 4, nextC3, 1);
        wcsncpy(charCurrentNext3Feature + 5, emptyStr, 1);
        *(featureList + featureIdx) = charCurrentNext3Feature;
        featureIdx++;
    }

    int preInFlag = 0; // 不仅指示是否进行双词匹配，也指示了匹配到的词汇的长度
    int preExFlag = 0;
    int postInFlag = 0;
    int postExFlag = 0;
    wchar_t *preIn = NULL;
    wchar_t *preEx = NULL;
    wchar_t *postIn = NULL;
    wchar_t *postEx = NULL;
    for (int l = cwsPredictionObj->constLabels->wordMax; l > cwsPredictionObj->constLabels->wordMin - 1; l--)
    {
        if (preInFlag == 0)
        {
            wchar_t *preInTmp = getSliceStr(text, idx - l + 1, l, nodeNum, emptyStr);
            if (wcscmp(preInTmp, emptyStr) != 0)
            {
                ret = set_hash_table_lookup(
                    cwsPredictionObj->UnigramSetHashTable, preInTmp,
                    cwsPredictionObj->unigramSetHashTableMaxSize);

                if (ret == 1)
                {
                    // 添加前一词特征
                    wchar_t *wordBeforeFeature = malloc((2 + l) * sizeof(wchar_t)); // 长度不定，如 “v中国”
                    wcsncpy(wordBeforeFeature, cwsPredictionObj->constLabels->wordBefore, 1);
                    wcsncpy(wordBeforeFeature + 1, preInTmp, l);
                    wcsncpy(wordBeforeFeature + 1 + l, emptyStr, 1);
                    *(featureList + featureIdx) = wordBeforeFeature;
                    featureIdx++;

                    // 记录该词
                    preIn = malloc(l * sizeof(wchar_t));
                    wcsncpy(preIn, preInTmp, l);
                    // preIn = preInTmp;
                    preInFlag = l;
                }
                // if (preInFlag == 0)
                free(preInTmp);
            }
            preInTmp = NULL;
        }

        if (postInFlag == 0)
        {
            wchar_t *postInTmp = getSliceStr(text, idx, l, nodeNum, emptyStr);

            if (wcscmp(postInTmp, emptyStr) != 0)
            {
                ret = set_hash_table_lookup(
                    cwsPredictionObj->UnigramSetHashTable, postInTmp,
                    cwsPredictionObj->unigramSetHashTableMaxSize);

                if (ret == 1)
                {
                    // 添加后一词特征
                    wchar_t *wordNextFeature = malloc((2 + l) * sizeof(wchar_t)); // 长度不定，如 “x中国”
                    wcsncpy(wordNextFeature, cwsPredictionObj->constLabels->wordNext, 1);
                    wcsncpy(wordNextFeature + 1, postInTmp, l);
                    wcsncpy(wordNextFeature + 1 + l, emptyStr, 1);
                    *(featureList + featureIdx) = wordNextFeature;
                    featureIdx++;

                    // 记录该词
                    postIn = malloc(l * sizeof(wchar_t));
                    wcsncpy(postIn, postInTmp, l);

                    postInFlag = l;
                }
                free(postInTmp);
            }
            postInTmp = NULL;
        }

        if (preExFlag == 0)
        {
            wchar_t *preExTmp = getSliceStr(text, idx - l, l, nodeNum, emptyStr);
            if (wcscmp(preExTmp, emptyStr) != 0)
            {
                ret = set_hash_table_lookup(
                    cwsPredictionObj->UnigramSetHashTable, preExTmp,
                    cwsPredictionObj->unigramSetHashTableMaxSize);

                if (ret == 1)
                {
                    // 记录该词
                    preEx = malloc(l * sizeof(wchar_t));
                    wcsncpy(preEx, preExTmp, l);

                    preExFlag = l;
                }
                free(preExTmp);
            }
            preExTmp = NULL;
        }

        if (postExFlag == 0)
        {
            wchar_t *postExTmp = getSliceStr(text, idx + 1, l, nodeNum, emptyStr);
            if (wcscmp(postExTmp, emptyStr) != 0)
            {
                ret = set_hash_table_lookup(
                    cwsPredictionObj->UnigramSetHashTable, postExTmp,
                    cwsPredictionObj->unigramSetHashTableMaxSize);

                if (ret == 1)
                {
                    // 记录该词
                    postEx = malloc(l * sizeof(wchar_t));
                    wcsncpy(postEx, postExTmp, l);

                    postExFlag = l;
                }
                free(postExTmp);
            }
            postExTmp = NULL;
        }
    }

    // 找到匹配的连续双词特征，此特征经过处理，仅保留具有歧义的连续双词
    if (preExFlag && postInFlag)
    {
        // printf("## add wl length feature %d %d.\n", preExFlag, postInFlag);
        wchar_t *bigramTmp = malloc((preExFlag + postInFlag + 2) * sizeof(wchar_t));
        wcsncpy(bigramTmp, preEx, preExFlag);
        wcsncpy(bigramTmp + preExFlag, cwsPredictionObj->constLabels->delim, 1);
        wcsncpy(bigramTmp + 1 + preExFlag, postIn, postInFlag);
        wcsncpy(bigramTmp + 1 + preExFlag + postInFlag, emptyStr, 1);

        ret = set_hash_table_lookup(
            cwsPredictionObj->BigramSetHashTable, bigramTmp,
            cwsPredictionObj->bigramSetHashTableMaxSize);

        if (ret == 1)
        {
            wchar_t *bigramLeft = malloc((preExFlag + postInFlag + 4) * sizeof(wchar_t));
            wcsncpy(bigramLeft, cwsPredictionObj->constLabels->word2Left, 2);
            wcsncpy(bigramLeft + 2, bigramTmp, preExFlag + postInFlag + 1);
            wcsncpy(bigramLeft + 3 + preExFlag + postInFlag, emptyStr, 1);

            *(featureList + featureIdx) = bigramLeft;
            featureIdx++;
        }

        free(bigramTmp);
        bigramTmp = NULL;

        // 添加词长特征
        wchar_t *bigramLeftLength = malloc(5 * sizeof(wchar_t));
        wcsncpy(bigramLeftLength, cwsPredictionObj->constLabels->word2Left, 2);
        wcsncpy(bigramLeftLength + 2, cwsPredictionObj->constLabels->wordLength + preExFlag - 2, 1);
        wcsncpy(bigramLeftLength + 3, cwsPredictionObj->constLabels->wordLength + postInFlag - 2, 1);
        wcsncpy(bigramLeftLength + 4, emptyStr, 1);
        *(featureList + featureIdx) = bigramLeftLength;
        featureIdx++;
    }

    if ((preInFlag != 0) && (postExFlag != 0))
    {
        // printf("## add wr length feature %d %d.\n", preInFlag, postExFlag);
        wchar_t *bigramTmp = malloc((preInFlag + postExFlag + 2) * sizeof(wchar_t));
        wcsncpy(bigramTmp, preIn, preInFlag);
        wcsncpy(bigramTmp + preInFlag, cwsPredictionObj->constLabels->delim, 1);
        wcsncpy(bigramTmp + 1 + preInFlag, postEx, postExFlag);
        wcsncpy(bigramTmp + 1 + preInFlag + postExFlag, emptyStr, 1);

        ret = set_hash_table_lookup(
            cwsPredictionObj->BigramSetHashTable, bigramTmp,
            cwsPredictionObj->bigramSetHashTableMaxSize);

        // printf("wr bigramTmp: %ls %d\n", bigramTmp, ret);
        if (ret == 1)
        {
            wchar_t *bigramRight = malloc((preInFlag + postExFlag + 4) * sizeof(wchar_t));
            wcsncpy(bigramRight, cwsPredictionObj->constLabels->word2Right, 2);
            wcsncpy(bigramRight + 2, bigramTmp, preInFlag + postExFlag + 1);
            wcsncpy(bigramRight + 3 + preInFlag + postExFlag, emptyStr, 1);

            *(featureList + featureIdx) = bigramRight;
            featureIdx++;
        }

        free(bigramTmp);
        bigramTmp = NULL;

        // 添加词长特征
        wchar_t *bigramRightLength = malloc(5 * sizeof(wchar_t));
        wcsncpy(bigramRightLength, cwsPredictionObj->constLabels->word2Right, 2);
        wcsncpy(bigramRightLength + 2, cwsPredictionObj->constLabels->wordLength + preInFlag - 2, 1);
        wcsncpy(bigramRightLength + 3, cwsPredictionObj->constLabels->wordLength + postExFlag - 2, 1);
        wcsncpy(bigramRightLength + 4, emptyStr, 1);
        *(featureList + featureIdx) = bigramRightLength;
        featureIdx++;
    }

    if (preIn != NULL)
    {
        free(preIn);
        preIn = NULL;
    }
    if (preEx != NULL)
    {
        free(preEx);
        preEx = NULL;
    }
    if (postIn != NULL)
    {
        free(postIn);
        postIn = NULL;
    }
    if (postEx != NULL)
    {
        free(postEx);
        postEx = NULL;
    }
    free(emptyStr);
    emptyStr = NULL;

    return featureList;
}

PyObject *getFeatureIndex(CwsPrediction *cwsPredictionObj,
                          wchar_t **featureList)
{
    int ret, index;
    int flag = 0;

    PyObject *indexList = PyList_New(0);
    int nodeFeatureLength = 0;

    while (*featureList) {
        index = dict_hash_table_lookup(
            cwsPredictionObj->featureToIdxDictHashTable,
            *featureList,
            cwsPredictionObj->featureToIdxDictHashTableMaxSize);
        PyObject *pyIndex = PyLong_FromLong(index);
        if (index != -1)
        {
            ret = PyList_Append(indexList, pyIndex);
        }
        else
        {
            flag = 1;
        }
        featureList = featureList + 1;
    }

    if (flag == 1)
    {
        PyObject *pyIndex = PyLong_FromLong(0);
        ret = PyList_Append(indexList, pyIndex);
    }

    return indexList;
}

int main() {

    Py_Initialize();
    // unsigned int res = set_hash_table_hash_str(L"一下子");
    unsigned int pos = dict_hash_table_hash_str(L"[END]") % 200000;
    CwsPrediction *cwsPredictionObj = newCwsPrediction();
    Init(cwsPredictionObj, 10000,
         "/home/cuichengyu/github/jiojio/jiojio/models/default_cws_model/unigram.txt",
         20000,
         "/home/cuichengyu/github/jiojio/jiojio/models/default_cws_model/bigram.txt",
         1000000,
         "/home/cuichengyu/github/jiojio/jiojio/models/default_cws_model/feature_to_idx.txt");

    const wchar_t *text = L"中国人真的很勤奋。";
    int textLength = wcslen(text);
    PyObject *featureList = Cut(cwsPredictionObj, text);

    Py_Finalize();
    return 0;
}
