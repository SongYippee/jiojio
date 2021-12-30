# -*- coding=utf-8 -*-

import json
import os
import pdb
import sys
from collections import Counter

from jiojio import logging, TimeIt, unzip_file, zip_file, read_file_by_iter
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

    def _create_features(self):
        self.start_feature = '[START]'
        self.end_feature = '[END]'

        self.delim = '.'
        self.empty_feature = '/'
        self.default_feature = '$$'

        # 为了减少字符串个数，缩短匹配时间，根据前后字符的位置，制定规则进行缩短匹配，规则如下：
        # c 代表 char，后一个位置 char 用 d 表示，前一个用 b 表示，按字母表顺序完成。
        # w 代表 word，后一个位置 word 用 x 表示，双词用 w 表示，
        self.char_current = 'c'
        self.char_before = 'b'  # 'c-1.'
        self.char_next = 'd'  # 'c1.'
        self.char_before_2 = 'a'  # 'c-2.'
        self.char_next_2 = 'e'  # 'c2.'
        self.char_before_current = 'bc'  # 'c-1c.'
        self.char_current_next = 'cd'  # 'cc1.'
        self.char_before_2_1 = 'ab'  # 'c-2c-1.'
        self.char_next_1_2 = 'de'  # 'c1c2.'

        self.word_before = 'v'  # 'w-1.'
        self.word_next = 'x'  # 'w1.'
        self.word_2_left = 'wl'  # 'ww.l.'
        self.word_2_right = 'wr'  # 'ww.r.'

        self.no_word = "**noWord"

    def build(self, train_file):

        # specials = set()
        word_length_info = Counter()  # 计算所有词汇长度信息
        feature_freq = Counter()  # 计算各个特征的出现次数，减少罕见特征计数
        unigrams = Counter()  # 计算各个 unigrams 出现次数，避免罕见 unigram 进入计数
        bigrams = Counter()  # 计算各个 bigrams 出现次数，避免罕见 bigram 进入计数
        for sample_idx, words in enumerate(read_file_by_iter(train_file)):

            if sample_idx % 100000 == 0:
                logging.info(sample_idx)
            # first pass to collect unigram and bigram and tag info
            word_length_info.update(map(len, words))
            # specials.update(word for word in words if len(word) >= 10)

            # 对文本进行归一化和整理
            if self.config.norm_text:
                words = [self.pre_processor(word) for word in words]

            example = ''.join(words)
            unigrams.update(words)

            for pre, suf in zip(words[:-1], words[1:]):
                bigrams.update([pre + '*' + suf])

            # second pass to get features
            for idx in range(len(example)):
                node_features = self.get_node_features(idx, example)
                feature_freq.update(feature for feature in node_features)

        # 对 self.unigram 的清理和整理
        # 若 self.unigram 中的频次都不足 feature_trim 则，在后续特征删除时必然频次不足
        self.unigram = set([unigram for unigram, freq in unigrams.most_common()
                            if freq > self.config.feature_trim])
        if '' in self.unigram:  # 删除错误 token
            self.unigram.remove('')

        # 对 self.bigram 的清理和整理
        self.bigram = set([bigram for bigram, freq in bigrams.most_common()
                           if freq > self.config.feature_trim])

        # 打印全语料不同长度词 token 的计数和比例
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
        # logging.info('special words num: {}\n'.format(specials))
        # logging.info(json.dumps(list(specials), ensure_ascii=False))

        logging.info('# orig feature num: {}'.format(len(feature_freq)))
        logging.info('# {:.2%} features are saved.'.format(
            sum([freq for _, freq in feature_freq.most_common()
                 if freq > self.config.feature_trim]) / sum(list(feature_freq.values()))))

        feature_set = [feature for feature, freq in feature_freq.most_common()
                       if freq > self.config.feature_trim]

        self.feature_to_idx = {feature: idx for idx, feature in enumerate(feature_set, 1)}

        # 特殊 token 须加入，如 空特征，起始特征，结束特征等
        self.feature_to_idx.update({self.empty_feature: 0})  # 空特征更新为第一个
        # self.feature_to_idx.update({self.start_feature: 1})  # 在寻找特征时已包含
        # self.feature_to_idx.update({self.end_feature: 2})
        logging.info('# true feature_num: {}'.format(len(self.feature_to_idx)))

        # create tag map
        B, B_single, I_first, I, I_end = self._create_label()
        tag_set = {B, B_single, I_first, I, I_end}
        self.tag_to_idx = {tag: idx for idx, tag in enumerate(sorted(tag_set))}
        assert self.tag_to_idx == {'B': 0, 'I': 1}, \
            'tag map must be like this for speeding up inferencing.'
        # self.idx_to_tag = FeatureExtractor._reverse_dict(self.tag_to_idx)

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
            feature_list.append(self.char_before_2_1 + before_c2 + self.delim + before_c)

        if idx < len(token_list) - 2:
            next_c2 = token_list[idx + 2]
            # 后第二字特征
            feature_list.append(self.char_next_2 + next_c2)
            # 后一字和后第二字组合
            feature_list.append(self.char_next_1_2 + next_c + self.delim + next_c2)

        # no num/letter based features
        if not self.config.word_feature:
            return feature_list

        # 2 * (wordMax-wordMin+1) word features (default: 2*(6-2+1)=10 )
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
        # 寻找连续两个词汇特征(该字在右侧词汇中)
        if pre_list_ex and post_list_in:  # 加速处理
            bigram = pre_list_ex + "*" + post_list_in
            if bigram in self.bigram:
                feature_list.append(self.word_2_left + bigram)

        # 寻找连续两个词汇特征(该字在左侧词汇中)
        if pre_list_in and post_list_ex:  # 加速处理
            bigram = pre_list_in + "*" + post_list_ex
            if bigram in self.bigram:
                feature_list.append(self.word_2_right + bigram)

        return feature_list

    def convert_feature_file_to_idx_file(self, feature_file,
                                         feature_idx_file, tag_idx_file):

        with open(feature_file, "r", encoding="utf8") as reader:
            with open(feature_idx_file, "w", encoding="utf8") as f_writer, \
                    open(tag_idx_file, "w", encoding="utf8") as t_writer:

                f_writer.write("{}\n\n".format(len(self.feature_to_idx)))
                t_writer.write("{}\n\n".format(len(self.tag_to_idx)))

                tags_idx = list()
                features_idx = list()
                while True:
                    line = reader.readline()
                    if line == '':
                        break
                    line = line.strip()
                    if not line:
                        # sentence finish
                        for feature_idx in features_idx:
                            if not feature_idx:
                                f_writer.write("0\n")
                            else:
                                f_writer.write(",".join(map(str, feature_idx)))
                                f_writer.write("\n")
                        f_writer.write("\n")

                        t_writer.write(",".join(map(str, tags_idx)))
                        t_writer.write("\n\n")

                        tags_idx = list()
                        features_idx = list()
                        continue

                    splits = json.loads(line)
                    feature_idx = [self.feature_to_idx[feat] for feat in splits[:-1]
                                   if feat in self.feature_to_idx]
                    features_idx.append(feature_idx)
                    tags_idx.append(self.tag_to_idx[splits[-1]])

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

    def convert_text_file_to_feature_file(
            self, text_file, conll_file, feature_file):
        # 从文本中，构建所有的特征和训练标注数据
        B, B_single, I_first, I, I_end = self._create_label()

        with open(conll_file, "w", encoding="utf8") as c_writer, \
                open(feature_file, "w", encoding="utf8") as f_writer:
            for words in read_file_by_iter(text_file):
                # 对文本进行归一化和整理
                if self.config.norm_text:
                    words = [self.pre_processor(word) for word in words]

                example, tags = word2tag(words)

                c_writer.write(json.dumps([example, tags], ensure_ascii=False) + "\n")

                for idx, tag in enumerate(tags):
                    features = self.get_node_features(idx, ''.join(example))
                    # 某些特征不存在，则将其转换为 `/` 特征
                    norm_features = [feature for feature in features if feature in self.feature_to_idx]
                    if len(norm_features) < len(features):
                        norm_features.append(self.empty_feature)

                    norm_features.append(tag)
                    f_writer.write(json.dumps(norm_features, ensure_ascii=False) + '\n')
                f_writer.write("\n")

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
