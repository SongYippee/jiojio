# distutils: language = c++
# cython: infer_types=True
# cython: language_level=3

import json
import os
import sys
import pickle
from collections import Counter

import jionlp as jio

from jiojio.config import config


def get_slice_str(iterable, start, length, all_len):
    # 截取字符串，其中，iterable 为字、词列表
    if start < 0 or start >= all_len:
        return ""
    if start + length >= all_len + 1:
        return ""

    return "".join(iterable[start: start + length])


def __get_node_features_idx(config, idx, nodes, feature_to_idx, unigram):
    feature_list = []
    i = idx
    length = len(nodes)
    word_max = config.wordMax
    word_min = config.wordMin
    word_range = word_max - word_min + 1

    c = nodes[i]

    # $$ starts feature
    feature_list.append(0)

    # 8 unigram/bgiram feature
    feat = 'c.' + c
    if feat in feature_to_idx:
        feature = feature_to_idx[feat]
        feature_list.append(feature)

    if i > 0:
        prev_c = nodes[i - 1]
        feat = 'c-1.' + prev_c
        if feat in feature_to_idx:
            feature = feature_to_idx[feat]
            feature_list.append(feature)

        feat = 'c-1c.' + prev_c + '.' + c
        if feat in feature_to_idx:
            feature = feature_to_idx[feat]
            feature_list.append(feature)

    if i + 1 < length:
        next_c = nodes[i + 1]

        feat = 'c1.' + next_c
        if feat in feature_to_idx:
            feature = feature_to_idx[feat]
            feature_list.append(feature)

        feat = 'cc1.' + c + '.' + next_c
        if feat in feature_to_idx:
            feature = feature_to_idx[feat]
            feature_list.append(feature)

    if i > 1:
        prepre_char = nodes[i - 2]
        feat = 'c-2.' + prepre_char
        if feat in feature_to_idx:
            feature = feature_to_idx[feat]
            feature_list.append(feature)

        feat = 'c-2c-1.' + prepre_char + '.' + nodes[i - 1]
        if feat in feature_to_idx:
            feature = feature_to_idx[feat]
            feature_list.append(feature)

    if i + 2 < length:
        feat = 'c2.' + nodes[i + 2]
        if feat in feature_to_idx:
            feature = feature_to_idx[feat]
            feature_list.append(feature)

    # no num/letter based features
    if not config.wordFeature:
        return feature_list

    # 2 * (wordMax-wordMin+1) word features (default: 2*(6-2+1)=10 )
    # the character starts or ends a word

    pre_list_in = []
    for l in range(word_max, word_min - 1, -1):
        # length 6 ... 2 (default)
        # "prefix including current c" token_list[n-l+1, n]
        # current character ends word
        tmp = get_slice_str(nodes, i - l + 1, l, length)
        if tmp in unigram:
            feat = 'w-1.' + tmp
            if feat in feature_to_idx:
                feature = feature_to_idx[feat]
                feature_list.append(feature)

            pre_list_in.append(tmp)
        else:
            pre_list_in.append("**noWord")

    post_list_in = []
    for l in range(word_max, word_min - 1, -1):
        # "suffix" token_list[n, n+l-1]
        # current character starts word
        tmp = get_slice_str(nodes, i, l, length)
        if tmp in unigram:
            feat = 'w1.' + tmp
            if feat in feature_to_idx:
                feature = feature_to_idx[feat]
                feature_list.append(feature)

            post_list_in.append(tmp)
        else:
            post_list_in.append("**noWord")

    # these are not in feature list
    prelst_ex = []
    for l in range(word_max, word_min - 1, -1):
        # "prefix excluding current c" token_list[n-l, n-1]
        tmp = get_slice_str(nodes, i - l, l, length)
        if tmp in unigram:
            prelst_ex.append(tmp)
        else:
            prelst_ex.append("**noWord")

    postlst_ex = []
    for l in range(word_max, word_min - 1, -1):
        # "suffix excluding current c" token_list[n+1, n+l]
        tmp = get_slice_str(nodes, i + 1, l, length)
        if tmp in unigram:
            postlst_ex.append(tmp)
        else:
            postlst_ex.append("**noWord")

    # this character is in the middle of a word
    # 2*(wordMax-wordMin+1)^2 (default: 2*(6-2+1)^2=50)

    for pre in prelst_ex:
        for post in post_list_in:
            feat = 'ww.l.' + pre + '*' + post
            if feat in feature_to_idx:
                feature = feature_to_idx[feat]
                feature_list.append(feature)

    for pre in pre_list_in:
        for post in postlst_ex:
            feat = 'ww.r.' + pre + '*' + post
            if feat in feature_to_idx:
                feature = feature_to_idx[feat]
                feature_list.append(feature)

    return feature_list


class FeatureExtractor:
    keywords = "-._,|/*:"

    num = set("0123456789." "几二三四五六七八九十千万亿兆零" "１２３４５６７８９０％")
    letter = set(
        "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ" "ａｂｃｄｅｆｇｈｉｇｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ" "／・－"
    )

    keywords_translate_table = str.maketrans("-._,|/*:", "&&&&&&&&")

    @classmethod
    def keyword_rename(cls, text):
        return text.translate(cls.keywords_translate_table)

    @classmethod
    def _num_letter_normalize_char(cls, character):
        if character in cls.num:
            return "**Num"
        if character in cls.letter:
            return "**Letter"
        return character

    @classmethod
    def normalize_text(cls, text):
        text = cls.keyword_rename(text)
        for character in text:
            if config.numLetterNorm:
                yield cls._num_letter_normalize_char(character)
            else:
                yield character

    def __init__(self):
        self.unigram = set()  # Set[str]
        self.bigram = set()  # Set[str]
        self.feature_to_idx = dict()  # Dict[str, int]
        self.tag_to_idx = dict()  # Dict[str, int]

    def build(self, train_file):
        examples = list()  # List[List[List[str]]]

        # first pass to collect unigram and bigram and tag info
        word_length_info = Counter()
        specials = set()
        for words in jio.read_file_by_iter(train_file):

            # line = self.keyword_rename(line)
            # e.g., '\ra \t　b \r\n'.split() = ['a', 'b']

            word_length_info.update(map(len, words))
            specials.update(word for word in words if len(word) >= 10)
            self.unigram.update(words)

            for pre, suf in zip(words[:-1], words[1:]):
                self.bigram.add("{}*{}".format(pre, suf))

            example = [self._num_letter_normalize_char(character)
                       for word in words for character in word]
            examples.append(example)

        max_word_length = max(word_length_info.keys())
        for length in range(1, max_word_length + 1):
            print("length = {} : {}".format(length, word_length_info[length]))
        # print('special words: {}'.format(', '.join(specials)))
        # second pass to get features

        feature_freq = Counter()

        for example in examples:
            for i, _ in enumerate(example):
                node_features = self.get_node_features(i, example)
                feature_freq.update(
                    feature for feature in node_features if feature != "/")

        feature_set = (feature for feature, freq in feature_freq.most_common()
                       if freq > config.featureTrim)

        tot = len(self.feature_to_idx)
        for feature in feature_set:
            if feature not in self.feature_to_idx:
                self.feature_to_idx[feature] = tot
                tot += 1
        # self.feature_to_idx = {
        #     feature: idx for idx, feature in enumerate(feature_set)
        # }

        if config.nLabel == 2:
            B = B_single = "B"
            I_first = I = I_end = "I"
        elif config.nLabel == 3:
            B = B_single = "B"
            I_first = I = "I"
            I_end = "I_end"
        elif config.nLabel == 4:
            B = "B"
            B_single = "B_single"
            I_first = I = "I"
            I_end = "I_end"
        elif config.nLabel == 5:
            B = "B"
            B_single = "B_single"
            I_first = "I_first"
            I = "I"
            I_end = "I_end"

        tag_set = {B, B_single, I_first, I, I_end}
        self.tag_to_idx = {tag: idx for idx, tag in enumerate(sorted(tag_set))}

    def get_node_features_idx(self, idx, nodes):
        return self.__get_node_features_idx(
            config, idx, nodes, self.feature_to_idx, self.unigram)

    def get_node_features(self, idx, token_list):
        # 给定一个  token_list，找出其中 token_list[idx] 匹配到的所有特征
        length = len(token_list)
        w = token_list[idx]
        feature_list = list()

        # 1 start feature
        feature_list.append("$$")

        # 8 unigram/bgiram feature
        # 当前字特征
        feature_list.append(''.join(['c.', w]))

        # 前一个字特征
        if idx > 0:
            feature_list.append(''.join(['c-1.', token_list[idx - 1]]))
        else:
            feature_list.append("/")

        # 后一个字特征
        if idx < len(token_list) - 1:
            feature_list.append(''.join(['c1.', token_list[idx + 1]]))
        else:
            feature_list.append("/")

        # 前第二字特征
        if idx > 1:
            feature_list.append(''.join(['c-2.', token_list[idx - 2]]))
        else:
            feature_list.append("/")

        # 后第二字特征
        if idx < len(token_list) - 2:
            feature_list.append(''.join(['c2.', token_list[idx + 2]]))
        else:
            feature_list.append("/")

        # 当前字和前一字组合特征
        if idx > 0:
            feature_list.append(
                ''.join(['c-1c.', token_list[idx - 1], config.delimInFeature, w]))
        else:
            feature_list.append("/")

        # 当前字和后一字组合特征
        if idx < len(token_list) - 1:
            feature_list.append(
                ''.join(['cc1.', w, config.delimInFeature, token_list[idx + 1]]))
        else:
            feature_list.append("/")

        # 前一字和前第二字组合
        if idx > 1:
            feature_list.append(
                ''.join(["c-2c-1.", token_list[idx - 2], config.delimInFeature, token_list[idx - 1]]))
        else:
            feature_list.append("/")

        # 后一字和后第二字组合
        if idx < len(token_list) - 2:
            feature_list.append(
                ''.join(["c1c2.", token_list[idx + 1], config.delimInFeature, token_list[idx + 2]]))
        else:
            feature_list.append("/")

        # no num/letter based features
        if not config.wordFeature:
            return feature_list

        # 2 * (wordMax-wordMin+1) word features (default: 2*(6-2+1)=10 )
        # the character starts or ends a word

        # 寻找该字前一个词汇特征(包含该字)
        pre_list_in = list()
        for l in range(config.wordMax, config.wordMin - 1, -1):
            # length 6 ... 2 (default)
            # "prefix including current c" token_list[n-l+1, n]
            # current character ends word
            tmp = get_slice_str(token_list, idx - l + 1, l, length)
            if tmp != "" and (tmp in self.unigram):
                feature_list.append("w-1." + tmp)
                pre_list_in.append(tmp)
            else:
                feature_list.append("/")
                pre_list_in.append("**noWord")

        # 寻找该字后一个词汇特征(包含该字)
        post_list_in = list()
        for l in range(config.wordMax, config.wordMin - 1, -1):
            # "suffix" token_list[n, n+l-1]
            # current character starts word
            tmp = get_slice_str(token_list, idx, l, length)
            if tmp != "" and (tmp in self.unigram):
                feature_list.append("w1." + tmp)
                post_list_in.append(tmp)
            else:
                feature_list.append("/")
                post_list_in.append("**noWord")

        # 寻找该字前一个词汇特征(不包含该字)
        pre_list_ex = list()
        for l in range(config.wordMax, config.wordMin - 1, -1):
            # "prefix excluding current c" token_list[n-l, n-1]
            tmp = get_slice_str(token_list, idx - l, l, length)
            if tmp != "" and (tmp in self.unigram):
                pre_list_ex.append(tmp)
            else:
                pre_list_ex.append("**noWord")

        # 寻找该字后一个词汇特征(不包含该字)
        post_list_ex = list()  # 其中个数由 wordMax 决定
        for l in range(config.wordMax, config.wordMin - 1, -1):
            # "suffix excluding current c" token_list[n+1, n+l]
            tmp = get_slice_str(token_list, idx + 1, l, length)
            if tmp != "" and (tmp in self.unigram):
                post_list_ex.append(tmp)
            else:
                post_list_ex.append("**noWord")

        # this character is in the middle of a word
        # 2 * (wordMax - wordMin + 1) ^ 2 (default: 2 * (6 -2 + 1) ^ 2 = 50)

        # 寻找连续两个词汇特征(该字在右侧词汇中)
        for pre in pre_list_ex:
            for post in post_list_in:
                bigram = pre + "*" + post
                if bigram in self.bigram:
                    feature_list.append("ww.l." + bigram)
                else:
                    feature_list.append("/")

        # 寻找连续两个词汇特征(该字在左侧词汇中)
        for pre in pre_list_in:
            for post in post_list_ex:
                bigram = pre + "*" + post
                if bigram in self.bigram:
                    feature_list.append("ww.r." + bigram)
                else:
                    feature_list.append("/")

        return feature_list

    def convert_feature_file_to_idx_file(
            self, feature_file, feature_idx_file, tag_idx_file):

        with open(feature_file, "r", encoding="utf8") as reader:
            # lines = reader.readlines()

            with open(feature_idx_file, "w", encoding="utf8") as f_writer, \
                    open(tag_idx_file, "w", encoding="utf8") as t_writer:

                f_writer.write("{}\n\n".format(len(self.feature_to_idx)))
                t_writer.write("{}\n\n".format(len(self.tag_to_idx)))

                tags_idx = list()  # List[str]
                features_idx = list()  # List[List[str]]
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

    def convert_text_file_to_feature_file(
            self, text_file, conll_file=None, feature_file=None):
        # 从文本中，构建所有的特征和训练标注数据

        if conll_file is None:
            conll_file = "{}.conll{}".format(*os.path.split(text_file))
        if feature_file is None:
            feature_file = "{}.feat{}".format(*os.path.split(text_file))

        if config.nLabel == 2:
            B = B_single = "B"
            I_first = I = I_end = "I"
        elif config.nLabel == 3:
            B = B_single = "B"
            I_first = I = "I"
            I_end = "I_end"
        elif config.nLabel == 4:
            B = "B"
            B_single = "B_single"
            I_first = I = "I"
            I_end = "I_end"
        elif config.nLabel == 5:
            B = "B"
            B_single = "B_single"
            I_first = "I_first"
            I = "I"
            I_end = "I_end"

        with open(conll_file, "w", encoding="utf8") as c_writer, \
                open(feature_file, "w", encoding="utf8") as f_writer:
            for words in jio.read_file_by_iter(text_file):

                # words = self.keyword_rename(line).split()
                example = list()
                tags = list()
                example, tags = jio.cws.word2tag(words)

                if config.numLetterNorm:
                    example = [self._num_letter_normalize_char(c)
                               for c in example]

                c_writer.write(json.dumps([example, tags]) + "\n")

                for idx, tag in enumerate(tags):
                    features = self.get_node_features(idx, example)
                    # 某些特征不存在，则将其转换为 `/` 特征
                    features = [
                        (feature if feature in self.feature_to_idx else "/")
                        for feature in features]
                    features.append(tag)
                    f_writer.write(json.dumps(features) + '\n')
                f_writer.write("\n")

    def save(self, model_dir=None):
        if model_dir is None:
            model_dir = config.modelDir

        data = dict()
        data["unigram"] = sorted(list(self.unigram))
        data["bigram"] = sorted(list(self.bigram))
        data["feature_to_idx"] = self.feature_to_idx
        data["tag_to_idx"] = self.tag_to_idx

        with open(os.path.join(model_dir, 'features.pkl'), 'wb') as fw:
            pickle.dump(data, fw, protocol=pickle.HIGHEST_PROTOCOL)

        # with open(os.path.join(config.modelDir, "features.json"), "w",
        #           encoding="utf8") as writer:
        #     json.dump(data, writer, ensure_ascii=False)

    @ classmethod
    def load(cls, model_dir=None):
        if model_dir is None:
            model_dir = config.modelDir

        extractor = cls.__new__(cls)

        feature_path = os.path.join(model_dir, "features.pkl")
        if os.path.exists(feature_path):
            with open(feature_path, "rb") as reader:
                data = pickle.load(reader)

            extractor.unigram = set(data["unigram"])
            extractor.bigram = set(data["bigram"])
            extractor.feature_to_idx = data["feature_to_idx"]
            extractor.tag_to_idx = data["tag_to_idx"]

            return extractor

        print("WARNING: features.pkl does not exist, try loading features.json", file=sys.stderr)

        feature_path = os.path.join(model_dir, "features.json")
        if os.path.exists(feature_path):
            with open(feature_path, "r", encoding="utf8") as reader:
                data = json.load(reader)
            extractor.unigram = set(data["unigram"])
            extractor.bigram = set(data["bigram"])
            extractor.feature_to_idx = data["feature_to_idx"]
            extractor.tag_to_idx = data["tag_to_idx"]
            extractor.save(model_dir)
            return extractor

        print("WARNING: features.json does not exist, try loading using old format", file=sys.stderr)

        with open(os.path.join(model_dir, "unigram_word.txt"), "r", encoding="utf8") as reader:
            extractor.unigram = set([line.strip() for line in reader])

        with open(os.path.join(model_dir, "bigram_word.txt"), "r", encoding="utf8") as reader:
            extractor.bigram = set(line.strip() for line in reader)

        extractor.feature_to_idx = {}
        feature_base_name = os.path.join(model_dir, "featureIndex.txt")
        for i in range(10):
            with open("{}_{}".format(feature_base_name, i), "r", encoding="utf8") as reader:
                for line in reader:
                    feature, index = line.split(" ")
                    feature = ".".join(feature.split(".")[1:])
                    extractor.feature_to_idx[feature] = int(index)

        extractor.tag_to_idx = {}
        with open(os.path.join(model_dir, "tagIndex.txt"), "r", encoding="utf8") as reader:
            for line in reader:
                tag, index = line.split(" ")
                extractor.tag_to_idx[tag] = int(index)

        print("INFO: features.json is saved", file=sys.stderr)
        extractor.save(model_dir)

        return extractor
