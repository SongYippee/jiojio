# -*- coding=utf-8 -*-

import json
import os
import pdb
import sys
from collections import Counter


from jiojio import logging, TimeIt, unzip_file, zip_file, \
    read_file_by_iter, get_node_features_c
from jiojio.tag_words_converter import word2tag
from jiojio.tag_words_converter import tag2word
from jiojio.pre_processor import PreProcessor


def get_slice_str(iterator_obj, start, length, all_len):
    # 截取字符串，其中，iterable 为字、词列表

    # 此逻辑非必须，python 默认当索引越界时，按 空 返回
    # if start < 0 or start >= all_len:
    #     return ""

    # 此逻辑非必须，若结尾索引大于总长度，则按 最长长度返回
    # if start + length > all_len:
    #     return ""

    return iterator_obj[start: start + length]

    # if type(iterator_obj) is str:
    #     return iterator_obj[start: start + length]
    # else:
    #     return "".join(iterator_obj[start: start + length])


class FeatureExtractor(object):

    def __init__(self, config):
        self.unigram = set()
        self.bigram = set()
        self.feature_to_idx = dict()
        self.tag_to_idx = dict()
        self.pre_processor = PreProcessor(
            convert_num_letter=config.convert_num_letter,
            normalize_num_letter=config.normalize_num_letter,
            convert_exception=config.convert_exception)

        self.config = config
        self._create_features()

        if get_node_features_c is None:
            self.get_node_features_c = None
        else:
            self.get_node_features_c = True

    def _create_features(self):
        self.start_feature = '[START]'
        self.end_feature = '[END]'

        self.delim = '.'
        self.empty_feature = '/'
        self.default_feature = '$$'

        # 为了减少字符串个数，缩短匹配时间，根据前后字符的位置，制定规则进行缩短匹配，规则如下：
        # c 代表 char，后一个位置 char 用 d 表示，前一个用 b 表示，按字母表顺序完成。
        # w 代表 word，后一个位置 word 用 x 表示，双词用 w 表示，
        seg = ''
        self.char_current = 'c' + seg
        self.char_before = 'b' + seg  # 'c-1.'
        self.char_next = 'd' + seg  # 'c1.'
        self.char_before_2 = 'a' + seg  # 'c-2.'
        self.char_next_2 = 'e' + seg  # 'c2.'
        self.char_before_3 = 'z' + seg  # 'c-3.
        self.char_next_3 = 'f' + seg  # 'c3.'
        self.char_before_current = 'bc' + seg  # 'c-1c.'
        self.char_before_2_current = 'ac' + seg  # 'c-2c'
        self.char_before_3_current = 'zc' + seg  # 'c-3c'
        self.char_current_next = 'cd' + seg  # 'cc1.'
        self.char_current_next_2 = 'ce' + seg  # 'cc2.'
        self.char_current_next_3 = 'cf' + seg  # 'cc3.'
        self.char_before_2_1 = 'ab' + seg  # 'c-2c-1.'
        self.char_next_1_2 = 'de' + seg  # 'c1c2.'

        self.word_before = 'v' + seg  # 'w-1.'
        self.word_next = 'x' + seg  # 'w1.'
        self.word_2_left = 'wl' + seg  # 'ww.l.'
        self.word_2_right = 'wr' + seg  # 'ww.r.'

        self.no_word = "nw" + seg
        self.length_feature_pattern = '{}{}'

    @staticmethod
    def _print_word_freq_info(word_length_info):
        short_token_total_length = 0
        total_length = sum(list(word_length_info.values()))
        logging.info("token length\ttoken num\tratio:")
        for length in range(1, 12):
            if length <= 10:
                short_token_total_length += word_length_info[length]
                logging.info("\t{} \t {} \t {:.2%}".format(
                    length, word_length_info[length],
                    word_length_info[length] / total_length))
            else:
                logging.info("\t{}+\t {} \t {:.2%}".format(
                    length, total_length - short_token_total_length,
                    (total_length - short_token_total_length) / total_length))

    def cleansing_unigrams(self, unigrams):
        clean_unigrams = dict()
        total_freq = 0
        clean_freq = 0
        for word, freq in unigrams.most_common():
            total_freq += freq

            if freq < self.config.unigram_feature_trim:
                continue
            if not self.pre_processor.check_chinese_char(word):
                continue
            if len(word) >= 10:
                continue
            if self.pre_processor.num_pattern.search(word):
                continue
            if '@' in word or '，' in word or '·' in word or word == '':
                # @ 往往为网名微博起始：@小狗狗爱吃糖
                # ， 往往为数字错误
                # · 往往为外文名：奥拉·新德丝
                continue

            if freq < 500:  # 低频中有大量不常见人名，须删除
                if self.pre_processor.check_chinese_name(word):
                    # print(word)
                    # pdb.set_trace()
                    continue

            clean_unigrams.update({word: freq})
            clean_freq += freq

        return clean_unigrams, clean_freq / total_freq

    def build(self, train_file):

        word_length_info = Counter()  # 计算所有词汇长度信息
        unigrams = Counter()  # 计算各个 unigrams 出现次数，避免罕见 unigram 进入计数
        # 计算各个 bigrams 出现次数，避免罕见 bigram 进入计数，该内容非常鸡肋，且极为稀疏
        # 因此，仅考虑出现模糊情况的双词特征，数量较少
        bigrams = Counter()

        # 第一次遍历统计获取 self.unigram 与所有词长 word_length_info
        for sample_idx, words in enumerate(read_file_by_iter(train_file)):

            if sample_idx % 1e6 == 0:
                logging.info(sample_idx)

            word_length_info.update(map(len, words))

            # 对文本进行归一化和整理
            if self.config.norm_text:
                words = [self.pre_processor(word) for word in words]

            unigrams.update(words)

        # 打印全语料不同长度词 token 的计数和比例
        FeatureExtractor._print_word_freq_info(word_length_info)

        # 对 self.unigram 的清理和整理
        logging.info('orig unigram num: {}'.format(len(unigrams)))
        clean_unigrams, unigram_ratio = self.cleansing_unigrams(unigrams)
        logging.info('{:.2%} unigram features are saved.'.format(unigram_ratio))
        # clean_unigrams = dict(unigrams.most_common())  # 不做任何处理

        # 若 self.unigram 中的频次都不足 unigram_feature_trim 则，在后续特征删除时必然频次不足
        self.unigram = set([unigram for unigram, freq in clean_unigrams.items()])
        logging.info('true unigram num: {}'.format(len(self.unigram)))

        # 对 self.bigram 的构建
        # 1、bigram 的构建分为两套，见 get_node_feature 中注释的分析
        # 2、步骤为，所有相邻的词对长度特征，得到特征如下：
        # wl12, wl22, wl34, wl72, wr24, wr32 等等，共计 (9*9)*2
        bigram_len_feature = list()
        for i in range(1, 10):
            for j in range(1, 10):
                bigram_len_feature.append(self.word_2_left + str(i) + str(j))
                bigram_len_feature.append(self.word_2_right + str(i) + str(j))

        # 3、统计获取所有带歧义词对特征，即 “亲口交代工作业务” 例中情况
        # 目前已获取 unigrams，数量远远少于原先的 unigrams，原先包含大量的特例化的数字、人名等

        # 第二次循环获取双词特征
        for sample_idx, words in enumerate(read_file_by_iter(train_file)):

            if sample_idx % 1e6 == 0:
                logging.info(sample_idx)

            # 对文本进行归一化和整理
            if self.config.norm_text:
                words = [self.pre_processor(word) for word in words]

            for pre, suf in zip(words[:-1], words[1:]):

                if pre in self.unigram:
                    flag = False
                    for i in range(3, 0, -1):
                        ambigu = pre[-1] + suf[:i]
                        if ambigu in self.unigram:
                            flag = True
                            break

                    if flag:
                        # print(pre, suf, ambigu)
                        # pdb.set_trace()
                        bigrams.update([pre + '*' + suf])
                        continue

                if suf in self.unigram:
                    flag = False
                    for i in range(3, 0, -1):
                        ambigu = pre[len(pre) - i:] + suf[0]
                        if ambigu in self.unigram:
                            flag = True
                            break

                    if flag:
                        bigrams.update([pre + '*' + suf])
                        continue

        # 若 self.bigram 中的频次都不足 bigram_feature_trim 则，在后续特征删除时必然频次不足
        logging.info('orig bigram num: {}'.format(len(bigrams)))
        logging.info('# {:.2%} bigram features are saved.'.format(
            sum([freq for _, freq in bigrams.most_common()
                 if freq > self.config.bigram_feature_trim]) / sum(list(bigrams.values()))))
        self.bigram = set([bigram for bigram, freq in bigrams.items()
                           if freq > self.config.bigram_feature_trim])
        logging.info('true bigram num: {}'.format(len(self.bigram)))

        # 第三次循环获取样本所有特征
        feature_freq = Counter()  # 计算各个特征的出现次数，减少罕见特征计数
        for sample_idx, words in enumerate(read_file_by_iter(train_file)):

            if sample_idx % 1e5 == 0:
                logging.info(sample_idx)

            # 对文本进行归一化和整理
            if self.config.norm_text:
                words = [self.pre_processor(word) for word in words]

            example = ''.join(words)
            # second pass to get features
            if self.get_node_features_c is None:
                for idx in range(len(example)):
                    node_features = self.get_node_features(idx, example)
                    feature_freq.update(feature for feature in node_features)
            else:
                example_length = len(example)
                print(example)
                for idx in range(example_length):
                    node_features = get_node_features_c(
                        idx, example, example_length, self.unigram, self.bigram)
                    feature_freq.update(feature for feature in node_features)
                    # print(idx, node_features)
                print(example)
                print(sample_idx, '\n')

        # pdb.set_trace()
        logging.info('# orig feature num: {}'.format(len(feature_freq)))
        # feature_set = [feature for feature, freq in feature_freq.most_common()
        #                if freq > self.config.feature_trim]

        feature_set = list()
        feature_count_sum = 0
        for feature, freq in feature_freq.most_common():
            if feature.startswith(self.char_before_3_current) or feature.startswith(self.char_current_next_3):
                if freq > self.config.gap_3_feature_trim:
                    feature_set.append(feature)
                    feature_count_sum += freq
            elif feature.startswith(self.char_before_2_current) or feature.startswith(self.char_current_next_2):
                if freq > self.config.gap_2_feature_trim:
                    feature_set.append(feature)
                    feature_count_sum += freq
            elif feature.startswith(self.char_before_current) or feature.startswith(self.char_current_next):
                if freq > self.config.gap_1_feature_trim:
                    feature_set.append(feature)
                    feature_count_sum += freq
            elif feature.startswith(self.word_2_left) or feature.startswith(self.word_2_right):
                if freq > self.config.bigram_feature_trim:
                    feature_set.append(feature)
                    feature_count_sum += freq
            else:
                if freq > self.config.feature_trim:
                    feature_set.append(feature)
                    feature_count_sum += freq
        logging.info('# {:.2%} features are saved.'.format(
            feature_count_sum / sum(list(feature_freq.values()))))

        for len_feature in bigram_len_feature:
            if len_feature not in feature_set:
                feature_set.append(len_feature)
            else:
                # print(len_feature)
                pass

        # pdb.set_trace()
        self.feature_to_idx = {feature: idx for idx, feature in enumerate(feature_set, 1)}

        # 特殊 token 须加入，如 空特征，起始特征，结束特征等
        self.feature_to_idx.update({self.empty_feature: 0})  # 空特征更新为第一个
        logging.info('# true feature_num: {}'.format(len(self.feature_to_idx)))

        # create tag map
        B, B_single, I_first, I, I_end = self._create_label()
        tag_set = {B, B_single, I_first, I, I_end}
        self.tag_to_idx = {tag: idx for idx, tag in enumerate(sorted(tag_set))}
        assert self.tag_to_idx == {'B': 0, 'I': 1}, \
            'tag map must be like this for speeding up inferencing.'
        # self.idx_to_tag = FeatureExtractor._reverse_dict(self.tag_to_idx)
        # pdb.set_trace()

    def get_node_features(self, idx, token_list):
        # 给定一个  token_list，找出其中 token_list[idx] 匹配到的所有特征
        length = len(token_list)
        cur_c = token_list[idx]
        feature_list = list()

        # 1 start feature
        # feature_list.append(self.default_feature)  # 取消默认特征，仅有极微小影响

        # 8 unigram/bgiram feature
        # 当前字特征
        feature_list.append(self.char_current + cur_c)

        if idx > 0:
            before_c = token_list[idx - 1]
            # 前一个字 特征
            feature_list.append(self.char_before + before_c)
            # 当前字和前一字组合特征
            feature_list.append(self.char_before_current + before_c + self.delim + cur_c)
        else:
            # 字符为起始位特征
            feature_list.append(self.start_feature)

        if idx < len(token_list) - 1:
            next_c = token_list[idx + 1]
            # 后一个字特征
            feature_list.append(self.char_next + next_c)
            # 当前字和后一字组合特征
            feature_list.append(self.char_current_next + cur_c + self.delim + next_c)
        else:
            # 字符为终止位特征
            feature_list.append(self.end_feature)

        if idx > 1:
            before_c2 = token_list[idx - 2]
            # 前第二字特征
            feature_list.append(self.char_before_2 + before_c2)
            # 前一字和前第二字组合
            # feature_list.append(self.char_before_2_1 + before_c2 + self.delim + before_c)
            feature_list.append(self.char_before_2_current + before_c2 + self.delim + cur_c)

        if idx < len(token_list) - 2:
            next_c2 = token_list[idx + 2]
            # 后第二字特征
            feature_list.append(self.char_next_2 + next_c2)
            # 后一字和后第二字组合
            # feature_list.append(self.char_next_1_2 + next_c + self.delim + next_c2)
            feature_list.append(self.char_current_next_2 + cur_c + self.delim + next_c2)

        if idx > 2:
            before_c3 = token_list[idx - 3]
            # 前第三字特征
            feature_list.append(self.char_before_3 + before_c3)
            # 前三字和当前字组合
            feature_list.append(self.char_before_3_current + before_c3 + self.delim + cur_c)

        if idx < len(token_list) - 3:
            next_c3 = token_list[idx + 3]
            # 后第三字特征
            feature_list.append(self.char_next_3 + next_c3)
            # 当前字和后第三字组合
            feature_list.append(self.char_current_next_3 + cur_c + self.delim + next_c3)

        # the character starts or ends a word
        # 寻找该字前一个词汇特征(包含该字)
        pre_list_in = None
        # 寻找该字后一个词汇特征(包含该字)
        post_list_in = None
        # 寻找该字前一个词汇特征(不包含该字)
        pre_list_ex = None
        # 寻找该字后一个词汇特征(不包含该字)
        post_list_ex = None
        for l in range(self.config.word_max, self.config.word_min - 1, -1):
            # "suffix" token_list[n, n+l-1]
            # current character starts word
            if pre_list_in is None:
                pre_in_tmp = get_slice_str(token_list, idx - l + 1, l, length)
                if pre_in_tmp in self.unigram:
                    feature_list.append(self.word_before + pre_in_tmp)
                    pre_list_in = pre_in_tmp  # 列表或字符串，关系计算速度

            if post_list_in is None:
                post_in_tmp = get_slice_str(token_list, idx, l, length)
                if post_in_tmp in self.unigram:
                    feature_list.append(self.word_next + post_in_tmp)
                    post_list_in = post_in_tmp

            if pre_list_ex is None:
                pre_ex_tmp = get_slice_str(token_list, idx - l, l, length)
                if pre_ex_tmp in self.unigram:
                    pre_list_ex = pre_ex_tmp

            if post_list_ex is None:
                post_ex_tmp = get_slice_str(token_list, idx + 1, l, length)
                if post_ex_tmp in self.unigram:
                    post_list_ex = post_ex_tmp
            # else:
            #     post_list_in.append(self.no_word)

        # this character is in the middle of a word
        # 双词汇构建特征模式：
        # 以“女干事每月经过领导办公室” 中，“月”字为例：
        # “月”字符合的前后词汇特征为 wr -> “每月”和“经过”，同时也符合 wl ->“每”和“月经”，
        # 此时存在处理歧义，首先将词汇长度为 1 的剔除，即将 “每” 剔除。
        # 然后根据词汇特征仅得到一个特征
        # wr22: 其中 wr 表示该字在第一个词的末尾，2 和 2 分别表示两个词的长度
        # 若第一个词的词长为3，则其特征表示为
        # wl32: 其中 wl 表示该字在第二个词的起始，3 和 2 分别表示两个词的长度

        # 双词对特点分析：
        # 1、特征数量爆炸
        # unigram 中的常用词汇量大约在 10~20万之间，若考虑每一个词汇的前后关联关系，
        # 则存在巨量的词汇对，大约在 4w * 4w 对，这对于 CRF 模型是不现实的。
        # 若对词汇对做删减，如，以 数量 trim 参数= 5 来删除低频词汇，依然会丢弃大量的词汇对
        # 经统计而得，对于词汇 “觊觎” 而言，删除后的词汇数量仅三个，分别为：
        # "在*觊觎", "是*觊觎", "的*觊觎",
        # 但是在文本中进行统计，则可得到大量的词汇特征数十个，如：
        # 眈地觊觎，怪的觊觎，长期觊觎，多有觊觎，时是觊觎，方都觊觎，人可觊觎，平台觊觎，唐某觊觎
        # 即大量的词汇对特征未统计到，而统计得到的特征又过于稀疏，覆盖面很低。

        # 2、有歧义词汇数量不大，对于某些词汇，仅统计歧义部分即可
        # 另一方面，对于 “觊觎” 这个词汇，前后粘度非常高，不可能和前后字形成歧义词串，因此，
        # 词汇特征对于 “觊觎” 这个词是无意义的。该特征的有意义性体现在前后词汇存在歧义的情况，如上例
        # “女干事每月经过下属办公室门口总要亲口交代工作业务”，
        # 其中， “每月”、“月经”、“经过”、“亲口”、“口交”、“交代”、“代工”、“工作”、“作业”、“业务”
        # 此时，词汇对特征体现出作用。即，我们需要统计，对于 unigram 中的一个词，在多大比例上，
        # 会出现与前后字的粘度。此部分粘度词汇，依然需要词汇对特征，如下：
        # 对于 “代” 字，需要得到
        # wr "wr交代*工作"
        # wl "wl口交*代工"
        # 此部分词汇特征将会大大降低，个数应当限制极低，须进行二次统计。

        # 寻找连续两个词汇特征(该字在右侧词汇中)
        if pre_list_ex and post_list_in:  # 加速处理
            bigram = pre_list_ex + self.delim + post_list_in
            if bigram in self.bigram:
                feature_list.append(self.word_2_left + bigram)
            feature_list.append(
                self.word_2_left + self.length_feature_pattern.format(
                    len(pre_list_ex), len(post_list_in)))

        # 寻找连续两个词汇特征(该字在左侧词汇中)
        if pre_list_in and post_list_ex:  # 加速处理
            bigram = pre_list_in + self.delim + post_list_ex
            if bigram in self.bigram:
                feature_list.append(self.word_2_right + bigram)
            feature_list.append(
                self.word_2_right + self.length_feature_pattern.format(
                    len(pre_list_in), len(post_list_ex)))

        return feature_list

    def _create_label(self):
        if self.config.label_num == 2:
            B = B_single = "B"
            I_first = I = I_end = "I"
        elif self.config.label_num == 3:
            B = B_single = "B"
            I_first = I = "I"
            I_end = "I_end"
        elif self.config.label_num == 4:
            B = "B"
            B_single = "B_single"
            I_first = I = "I"
            I_end = "I_end"
        elif self.config.label_num == 5:
            B = "B"
            B_single = "B_single"
            I_first = "I_first"
            I = "I"
            I_end = "I_end"

        return B, B_single, I_first, I, I_end

    @staticmethod
    def _reverse_dict(dict_obj):
        return dict([(v, k) for k, v in dict_obj.items()])

    def convert_text_file_to_feature_idx_file(
            self, text_file, feature_idx_file, gold_idx_file):
        # 从文本中，构建所有的特征和训练标注数据
        B, B_single, I_first, I, I_end = self._create_label()

        with open(feature_idx_file, "w", encoding="utf8") as f_writer, \
                open(gold_idx_file, "w", encoding="utf8") as g_writer:

            f_writer.write("{}\n\n".format(len(self.feature_to_idx)))
            g_writer.write("{}\n\n".format(len(self.tag_to_idx)))

            for words in read_file_by_iter(text_file):
                # 对文本进行归一化和整理
                if self.config.norm_text:
                    words = [self.pre_processor(word) for word in words]

                example, tags = word2tag(words)
                tags_idx = list()

                for idx, tag in enumerate(tags):
                    features = self.get_node_features(idx, ''.join(example))
                    # 某些特征不存在，则将其转换为 `/` 特征
                    norm_features = [feature for feature in features if feature in self.feature_to_idx]
                    if len(norm_features) < len(features):
                        norm_features.append(self.empty_feature)


                    feature_idx = [self.feature_to_idx[feat] for feat in norm_features
                                   if feat in self.feature_to_idx]
                    tags_idx.append(self.tag_to_idx[tag])
                    # pdb.set_trace()
                    # norm_features.append(tag)
                    f_writer.write(",".join(map(str, feature_idx)))
                    f_writer.write("\n")
                f_writer.write("\n")
                g_writer.write(",".join(map(str, tags_idx)))
                g_writer.write('\n')

    def save(self, model_dir=None):
        if model_dir is None:
            model_dir = self.config.model_dir

        data = dict()
        data["unigram"] = sorted(list(self.unigram))
        data["bigram"] = sorted(list(self.bigram))
        data["feature_to_idx"] = self.feature_to_idx
        data["tag_to_idx"] = self.tag_to_idx

        feature_path = os.path.join(model_dir, "features.json")

        with open(feature_path, "w", encoding="utf8") as f_w:
            json.dump(data, f_w, ensure_ascii=False, indent=4, separators=(',', ':'))

        zip_file(feature_path)

    @classmethod
    def load(cls, config, model_dir=None):
        extractor = cls.__new__(cls)
        extractor.config = config
        extractor._create_features()

        feature_path = os.path.join(model_dir, "features.json")
        zip_feature_path = os.path.join(model_dir, "features.zip")

        if (not os.path.exists(feature_path)) and os.path.exists(zip_feature_path):
            logging.info('unzip `{}` to `{}`.'.format(zip_feature_path, feature_path))
            unzip_file(zip_feature_path)

        if os.path.exists(feature_path):
            with open(feature_path, "r", encoding="utf8") as reader:
                data = json.load(reader)

            extractor.unigram = set(data["unigram"])
            extractor.bigram = set(data["bigram"])
            extractor.feature_to_idx = data["feature_to_idx"]
            extractor.tag_to_idx = data["tag_to_idx"]

            # extractor.idx_to_tag = extractor._reverse_dict(extractor.tag_to_idx)
            return extractor

        logging.warn("WARNING: features.json does not exist, try loading using old format")
        with open(os.path.join(model_dir, "unigram_word.txt"), "r", encoding="utf8") as reader:
            extractor.unigram = set([line.strip() for line in reader])

        with open(os.path.join(model_dir, "bigram_word.txt"), "r", encoding="utf8") as reader:
            extractor.bigram = set(line.strip() for line in reader)

        extractor.feature_to_idx = dict()
        feature_base_name = os.path.join(model_dir, "featureIndex.txt")
        for i in range(10):
            with open("{}_{}".format(feature_base_name, i), "r", encoding="utf8") as reader:
                for line in reader:
                    feature, index = line.split(" ")
                    feature = ".".join(feature.split(".")[1:])
                    extractor.feature_to_idx[feature] = int(index)

        extractor.tag_to_idx = dict()
        with open(os.path.join(model_dir, "tagIndex.txt"), "r", encoding="utf8") as reader:
            for line in reader:
                tag, index = line.split(" ")
                extractor.tag_to_idx[tag] = int(index)

        return extractor
