#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Reads and writes the testcase requirements file
"""

from optparse import OptionParser
from collections import OrderedDict
import operator
import re
import sys
import os
import logging
import copy

class TestCaseReqts(object):
    TCD_HEADER = "'TESTNAME', 'REQUIREMENTS'"
    def __init__(self, tc_reqts_path):
        self.tc_reqts_filepath = tc_reqts_path

        self.tc_reqts = {}
        self.read_tc_reqts()

    def read_tc_reqts(self):
        logging.critical("Reading testcase requirements file '%s'."
                      % self.tc_reqts_filepath)
        with open(self.tc_reqts_filepath, 'r') as tcd_file:
            tcd_lines = [line.strip() for line in tcd_file.readlines()]

        if len(tcd_lines) == 0:
            raise ValueError("Requirements file %s empty!" %
                              self.tc_reqts_filepath)
        if not tcd_lines[0].startswith(self.TCD_HEADER):
            raise ValueError("Checklist line 0 does not start with '%s'." %
                          self.TCD_HEADER)

        for line_num, line in enumerate(tcd_lines[1:]):
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            if len(toks) != 2:
                raise ValueError("%s %d Line %s tok len %d"
                              % (self.tc_reqts_filepath,
                                 line_num+1, line, len(toks)))
            logging.info("Tokens: %s" % toks)
            tc_name = copy.deepcopy(toks[0])
            if (tc_name in self.tc_reqts):
                raise ValueError("%s %d Line Duplicate tc name %s\n"
                              % (self.tc_reqts_filepath,
                                 line_num+1, tc_name))
            tc_reqts = copy.deepcopy(toks[1])
            reqts = [tok.strip() for tok in tc_reqts.split(",")]
            if 0 == len(reqts):
                raise ValueError("%s %d Line TC name %s No Requirements?!!!\n"
                              % (self.tc_reqts_filepath,
                                 line_num+1, tc_name))
            self.tc_reqts[tc_name] = [reqts[0]];
            for reqt in reqts[1:]:
                if reqt in self.tc_reqts[tc_name]:
                    raise ValueError("%s %d TC %s Duplicate requirement %s\n"
                              % (self.tc_reqts_filepath,
                                 line_num+1, tc_name, reqt))
                self.tc_reqts[tc_name].append(reqt)

    def write_tc_reqts(self):
        print("%s" % self.TCD_HEADER)
        keys = sorted(self.tc_reqts.keys())
        if 0 == len(keys):
            raise ValueError("No testcase requirements to write...\n")
        for key in keys:
            print("'%s', '%s'" % (key, ','.join(self.tc_reqts[key])))

def create_parser():
    parser = OptionParser(description="Read and optionally write TC requirements file.")
    parser.add_option('-r', '--tc_reqts',
            dest = 'tc_reqts_filepath',
            action = 'store', type = 'string',
            default = 'Idle3_TC.txt',
            help = 'Testcase requirements file, manually edited',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if not os.path.isfile(options.tc_reqts_filepath):
        raise ValueError("TC requirements file '%s' does not exist." %
                         options.tc_reqts_filepath)

def main(argv = None):
    logging.basicConfig(level=logging.WARN)
    parser = create_parser()
    if argv is None:
        argv = sys.argv[1:]

    (options, argv) = parser.parse_args(argv)
    if len(argv) != 0:
        print('Invalid argument!')
        print
        parser.print_help()
        return -1

    try:
        validate_options(options)
    except ValueError as e:
        print(e)
        sys.exit(-1)

    tc_reqts = TestCaseReqts(options.tc_reqts_filepath)
    logging.critical("Writing testcase requirements.\n")
    tc_reqts.write_tc_reqts()

if __name__ == '__main__':
    sys.exit(main())
