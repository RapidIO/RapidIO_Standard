#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Reads and writes the testcase description file
"""

from optparse import OptionParser
from collections import OrderedDict
import operator
import re
import sys
import os
import logging
import copy

class TestCaseDescr(object):
    TCD_HEADER = "'TESTNAME', 'DESCRIPTION'"
    def __init__(self, tc_descr_path):
        self.tc_descr_filepath = tc_descr_path

        self.tc_descr = {}
        self.read_tc_descr()

    def read_tc_descr(self):
        logging.critical("Reading testcase descriptions file '%s'."
                      % self.tc_descr_filepath)
        with open(self.tc_descr_filepath, 'r') as tcd_file:
            tcd_lines = [line.strip() for line in tcd_file.readlines()]

        if len(tcd_lines) == 0:
            raise ValueError("Descriptions file %s empty!" %
                              self.tc_descr_filepath)

        if not tcd_lines[0].startswith(self.TCD_HEADER):
            raise ValueError("Checklist line 0 does not start with '%s'." %
                          self.TCD_HEADER)

        for line_num, line in enumerate(tcd_lines[1:]):
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            if len(toks) != 2:
                raise ValueError("%s %d Line %s tok len %d"
                              % (self.tc_descr_filepath,
                                 line_num+1, line, len(toks)))
            logging.info("Tokens: %s" % toks)
            tc_name = copy.deepcopy(toks[0])
            tc_descr = copy.deepcopy(toks[1])
            if (tc_name in self.tc_descr):
                raise ValueError("%s %d Line Duplicate tc name %s\n"
                              % (self.tc_descr_filepath,
                                 line_num+1, tc_name))
            self.tc_descr[tc_name] = tc_descr;

    def write_tc_descr(self):
        print("%s" % self.TCD_HEADER)
        keys = sorted(self.tc_descr.keys())
        if 0 == len(keys):
            raise ValueError("No testcase descriptions to write...\n")
        for key in keys:
            print("'%s', '%s'" % (key, self.tc_descr[key]))

def create_parser():
    parser = OptionParser(description="Read and optionally write TC description file.")
    parser.add_option('-d', '--tc_descr',
            dest = 'tc_descr_filepath',
            action = 'store', type = 'string',
            default = 'Idle3_TC_Descr.txt',
            help = 'Testcase description file, manually edited',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if not os.path.isfile(options.tc_descr_filepath):
        raise ValueError("TC descriptions file '%s' does not exist." %
                         options.tc_descr_filepath)

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

    tc_descr = TestCaseDescr(options.tc_descr_filepath)
    logging.critical("Writing testcase descriptions.\n")
    tc_descr.write_tc_descr()

if __name__ == '__main__':
    sys.exit(main())
