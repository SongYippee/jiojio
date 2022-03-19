# -*- coding=utf-8 -*-
# Library: jiojio
# Author: dongrixinyu
# License: GPL-3.0
# Email: dongrixinyu.89@163.com
# Github: https://github.com/dongrixinyu/jiojio
# Description: fast Chinese Word Segmentation(CWS) and Part of Speech(POS) based on CPU.'

import os
import pdb
import ctypes
import traceback

from .logger import set_logger
from .time_it import TimeIt
from .zip_file import unzip_file, zip_file
from .file_io import read_file_by_iter, write_file_by_line
from .trie_tree import TrieTree
