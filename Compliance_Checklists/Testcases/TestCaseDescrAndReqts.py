#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Support for the test case description and requirements file.
    Supports reading and writing that file, and merging the
    test case descrption and test case requirements files into
    this single file.

    The test case description and requirements file has the format:
    'testcase_name', 'testcase_description', 'requirements_list'
"""

from optparse import OptionParser
from collections import OrderedDict
import operator
import re
import sys
import os
import logging
import copy
from TestCaseDescr import TestCaseDescr
from TestCaseReqts import TestCaseReqts

class DescrReqts(object):
    def __init__(self, descr, reqts):
        self.descr = descr;
        self.reqts = reqts;

class TestCaseDescrAndReqts(object):
    D_AND_R_HEADER = "'TESTNAME', 'DESCRIPTION', 'REQUIREMENTS'"
    def __init__(self, d_and_r_filepath):
        self.d_and_r_filepath = d_and_r_filepath
        self.description_filepath = ''
        self.requirements_filepath = ''
        self.tc_d_and_r = {}
        if os.path.isfile(self.d_and_r_filepath):
            self.read_descriptions_and_requirements()

    def cross_check_descriptions_and_requirements(self):
        for tc_name in self.descr.tc_descr.keys():
            if tc_name not in self.reqts.tc_reqts:
                raise ValueError("Testcase '%s' not found in requirements." %
                                tc_name)
        for tc_name in self.reqts.tc_reqts.keys():
            if tc_name not in self.descr.tc_descr:
                raise ValueError("Testcase '%s' not found in descriptions." %
                                tc_name)

    def merge_descriptions_and_requirements(self, descr_fp, reqts_fp):
        self.description_filepath = descr_fp
        self.requirements_filepath = reqts_fp
        self.descr = TestCaseDescr(self.description_filepath)
        self.reqts = TestCaseReqts(self.requirements_filepath)
        self.cross_check_descriptions_and_requirements()
        self.tc_d_and_r = {}
        for tc_name in sorted(self.descr.tc_descr.keys()):
            self.tc_d_and_r[tc_name] = DescrReqts(self.descr.tc_descr[tc_name],
                                              self.reqts.tc_reqts[tc_name])

    def read_descriptions_and_requirements(self):
        logging.critical(
            "Reading testcase descriptions and requirements file '%s'."
            % self.d_and_r_filepath)

        with open(self.d_and_r_filepath, 'r') as tcd_file:
            tcd_lines = [line.strip() for line in tcd_file.readlines()]

        if len(tcd_lines) == 0:
            raise ValueError("Descriptions and requirements file %s empty!" %
                              self.d_and_r_filepath)

        if not tcd_lines[0].startswith(self.D_AND_R_HEADER):
            raise ValueError(
                      "Descriptions and requirements file line 0 is not '%s'." %
                      self.D_AND_R_HEADER)

        for line_num, line in enumerate(tcd_lines[1:]):
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            if len(toks) != 3:
                raise ValueError("%s %d Line %s tok len %d"
                              % (self.tc_descr_filepath,
                                 line_num+1, line, len(toks)))
            logging.info("Tokens: %s" % toks)
            tc_name = copy.deepcopy(toks[0])
            tc_descr = copy.deepcopy(toks[1])
            tc_reqts = copy.deepcopy(toks[2])
            if len(tc_name) == 0:
                raise ValueError("%s Line %d TC name is empty!\n"
                              % (self.tc_descr_filepath,
                                 line_num+1, tc_name))
            if (tc_name in self.tc_d_and_r):
                raise ValueError("%s Line %d Duplicate tc name %s\n"
                              % (self.tc_descr_filepath,
                                 line_num+1, tc_name))
            if len(tc_descr) == 0:
                raise ValueError("%s Line %d TC description is empty!\n"
                              % (self.tc_descr_filepath,
                                 line_num+1, tc_name))
            reqts = [tok.strip() for tok in tc_reqts.split(",")]
            if 0 == len(reqts):
                raise ValueError("%s Line %d TC name %s No Requirements?!!!\n"
                              % (self.tc_reqts_filepath, line_num+1, tc_name))
            chkd_reqts = [reqts[0]];
            for reqt in reqts[1:]:
                if reqt in chkd_reqts:
                    raise ValueError("%s Line %d TC %s Duplicate reqt %s\n"
                          % (self.tc_reqts_filepath, line_num+1, tc_name, reqt))
                chkd_reqts.append(reqt)
            self.tc_d_and_r[tc_name] = DescrReqts(tc_descr, chkd_reqts)

    def write_descriptions_and_requirements(self):
        print("%s" % self.D_AND_R_HEADER)
        for tc_name in sorted(self.tc_d_and_r.keys()):
            print ("'%s', '%s', '%s'" % (tc_name,
                 self.tc_d_and_r[tc_name].descr,
                 ",".join(self.tc_d_and_r[tc_name].reqts)))

def create_parser():
    parser = OptionParser(description="Merge testcase descriptions and requirements file, or read, check, sort and display testcase descriptions and requirements file.")
    parser.add_option('-r', '--requirements',
            dest = 'requirements_filepath',
            action = 'store', type = 'string',
            default = '',
            help = 'Testcase requirements file',
            metavar = 'FILE')
    parser.add_option('-d', '--descriptions',
            dest = 'descriptions_filepath',
            action = 'store', type = 'string',
            default = '',
            help = 'Testcase descriptions file',
            metavar = 'FILE')
    parser.add_option('-m', '--descr_and_reqts',
            dest = 'd_and_r_filepath',
            action = 'store', type = 'string',
            default = '',
            help = 'Testcase descriptions and requirements file',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if options.d_and_r_filepath != '':
        if not os.path.isfile(options.d_and_r_filepath):
            raise ValueError("Descr and Reqts file '%s' does not exist." %
                             options.d_and_r_filepath)
    if options.requirements_filepath != '':
        if not os.path.isfile(options.requirements_filepath):
            raise ValueError("Requirements file '%s' does not exist." %
                             options.requirements_filepath)
    if options.descriptions_filepath != '':
        if not os.path.isfile(options.descriptions_filepath):
            raise ValueError("Descriptions file '%s' does not exist." %
                             options.descriptions_filepath)

    if options.d_and_r_filepath != '':
        return

    if options.requirements_filepath == '' or options.descriptions_filepath == '':
        raise ValueError("Must enter both requirements and descriptions files.")

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
    
    tc_info = TestCaseDescrAndReqts(options.d_and_r_filepath)
    if options.d_and_r_filepath == '':
        tc_info.merge_descriptions_and_requirements(
                               options.descriptions_filepath,
                               options.requirements_filepath)
    tc_info.write_descriptions_and_requirements()

if __name__ == '__main__':
    sys.exit(main())
