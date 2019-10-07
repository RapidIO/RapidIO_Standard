#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Update the checklist database, which provides consistent references to
    all requirements and the merged_sorted_checklist.txt file evolves.

    - Import the existing merged_sorted_checklist.txt file, and the
      checklist_db.txt file.
    - Check to see which items in the merged_sorted_checklist.txt file have
      been changed with respect to the checklist_db.txt file,
      and modify references as required.
"""

from optparse import OptionParser
from collections import OrderedDict
import operator
import re
import sys
import os
import logging
import copy
import inspect
currentdir = os.getcwd()
parentdir = os.path.dirname(currentdir)
sys.path.insert(0,parentdir)
from constants import *
from create_translation import *
from TestCaseDescrAndReqts import TestCaseDescrAndReqts

class DescrReqtReqtDescr(object):
    def __init__(self, descr, reqt, reqt_descr):
         self.descr = descr
         self.reqt_list = {}
         self.reqt_list[reqt] = reqt_descr

class DB(object):
    def __init__(self, descr, revision, part, chapter, section, outline):
        self.descr = descr
        self.revision = revision
        self.part = part
        self.chapter = chapter
        self.section = section
        self.status = ''
        if revision in outline:
            if part in outline[revision]:
                if chapter in outline[revision][part]:
                    if section in outline[revision][part][chapter]:
                        self.status = 'Relevant'

class TC_D_R_RD(object):
    TC_D_R_RD_HEADER = "'TESTCASE', 'DESCRIPTION', 'REQUIREMENT', 'REQUIREMENT DESCRIPTION'"
    def __init__(self, tc_d_r_rd_filepath, tc_d_and_r_filepath, outline_filepath, database_filepath):
        self.tc_d_r_rd_filepath = tc_d_r_rd_filepath

        self.tc_d_and_r = ''
        self.db = {}
        self.outline_filepath = ''
        self.outline = {}
        self.db_revs = []
        self.tc_d_r_rd = {}
        self.tc_d_and_r_filepath = tc_d_and_r_filepath
        self.database_filepath = ''

        self.read_tc_d_r_rd(self.tc_d_r_rd_filepath)
        self.read_outline(outline_filepath)
        self.tc_d_and_r = TestCaseDescrAndReqts(tc_d_and_r_filepath)
        self.read_database(database_filepath)

    def read_database(self, database_filepath):
        if not os.path.isfile(database_filepath):
            return False
        self.database_filepath = database_filepath
        logging.critical("Reading database file '%s'."
                      % self.database_filepath)
        ## try:
        with open(self.database_filepath, 'r') as db_file:
            db_lines = [line.strip() for line in db_file.readlines()]
        ## except:
        ##     logging.critical("Failed reading database file '%s'"
        ##                      % self.database_filepath)
        ##     return True

        if not db_lines[0].startswith(MERGED_CHECKLIST_SORTED_SPEC_REVS):
            raise ValueError("Database line 0 does not start with '%s'." %
                          MERGED_CHECKLIST_SORTED_SPEC_REVS)
        self.db_revs = [item.strip() for item in
             db_lines[0][len(MERGED_CHECKLIST_SORTED_SPEC_REVS):].split(" ")]
        logging.info("Database file revs: %s" % ",".join(self.db_revs))

        if not db_lines[1].startswith(DATABASE_HEADER):
            raise ValueError("Database line 1 does not start with '%s'." %
                          DATABASE_HEADER)

        for line_num, line in enumerate(db_lines[2:]):
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            if not len(toks) >= TOK_IDX_DB_H_FIRST_SECN:
                raise ValueError("%d DB Line %s tok len %d"
                              % (line_num+1, line, len(toks)))
            uid = toks[TOK_IDX_DB_H_CONST_REF]
            if (uid in self.db):
                raise ValueError("Database line %d duplicate UID %s" %
                                 (line_num, uid))
            self.db[uid] = DB(toks[TOK_IDX_DB_H_SENTENCE],
                              toks[TOK_IDX_DB_H_REVISION],
                              toks[TOK_IDX_DB_H_PART],
                              toks[TOK_IDX_DB_H_CHAPTER],
                              toks[TOK_IDX_DB_H_SECTION],
                              self.outline)
        return False

    def _print_reqts(self, reqt_status):
        found_one = False
        for reqt in sorted(self.db.keys()):
            if (self.db[reqt].status == reqt_status):
               if (not found_one):
                   found_one = True
                   print("Reqt, Description, Revision, Part, Chapter, Section")
               print("'%s'" % "', '".join([reqt, self.db[reqt].descr,
                                                 self.db[reqt].revision,
                                                 self.db[reqt].part,
                                                 self.db[reqt].chapter,
                                                 self.db[reqt].section]))
        if not found_one:
            print("No requirements selected.")
        return

    def print_missing_reqts(self):
        self._print_reqts("Relevant");

    def print_tested_reqts(self):
        self._print_reqts("Tested");

    def read_tc_d_r_rd(self, tc_d_r_rd_filepath):
        if not os.path.isfile(tc_d_r_rd_filepath):
            return False

        logging.critical("Reading TC_D_R_RD file '%s'."
                      % self.tc_d_r_rd_filepath)
        try:
            with open(self.tc_d_r_rd_filepath) as tcdrrd_file:
                tcdrrd_lines = [l.strip() for l in tcdrrd_file.readlines()]
        except:
            logging.critical("Failed reading TC_D_R_RD file '%s', continuing..."
                             % self.tc_d_r_rd_filepath)
            return

        if not tcdrrd_lines[0].startswith(self.TC_D_R_RD_HEADER):
            raise ValueError("Database line 0 does not start with '%s'." %
                          self.TC_D_R_RD_HEADER)

        for line_num, line in enumerate(tcdrrd_lines[1:]):
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            if len(toks) != 4:
                raise ValueError("%s Line %d '%s' tok len %d Should be 4"
                              % (self.tc_d_r_rd_filepath,
                                 line_num+1, line, len(toks)))
            if not toks[0] in self.tc_d_r_rd:
                self.tc_d_r_rd[toks[0]] = DescrReqtReqtDescr(toks[1], toks[2],
                                                            toks[3])
                continue
            self.tc_d_r_rd[toks[0]].reqt_list[toks[2]] = toks[3]

    def write_tc_d_r_rd(self):
        logging.critical("Writing TC_D_R_RD file.")

        print("%s" % self.TC_D_R_RD_HEADER)
        for tc_name in sorted(self.tc_d_r_rd.keys()):
            for reqt in sorted(self.tc_d_r_rd[tc_name].reqt_list.keys()):
                print ("'%s', '%s', '%s', '%s'" % (
                     tc_name, self.tc_d_r_rd[tc_name].descr,
                     reqt, self.tc_d_r_rd[tc_name].reqt_list[reqt]))

    def read_outline(self, outline_filepath):
        if not os.path.isfile(outline_filepath):
            return False
        self.outline_filepath = outline_filepath
        try: 
            with open(self.outline_filepath, 'r') as new_sections:
                lines = [line.strip() for line in new_sections.readlines()]
        except:
            print("Failed reading outline file.")
            return True

        header_items = [item.strip() for item in OUTLINE_HEADER.split(",")]
        line_items = [item.strip() for item in lines[0][1:-1].split("', '")]
        if not header_items == line_items:
            raise ValueError("Outline bad format: File %s header is %s not %s"
                         % (self._new_sections_file, line_items, header_items))

        for x, line in enumerate(lines[1:]):
            tokens = [tok.strip() for tok in line.split("', '")]
            tokens = [re.sub("'", "", tok) for tok in tokens]
            if not len(tokens) == len(header_items):
                raise ValueError("File %s Line %d %d bad format: '%s'"
                            % (self._new_sections_file, x, len(tokens), line))
            revision = tokens[TOK_IDX_OUTLINE_REV]
            part = tokens[TOK_IDX_OUTLINE_PART]
            chapter = tokens[TOK_IDX_OUTLINE_CHAPTER]
            section = tokens[TOK_IDX_OUTLINE_SECTION]
            if not revision in self.outline:
                self.outline[revision] = {}
            if not part in self.outline[revision]:
                self.outline[revision][part] = {}
            if not chapter in self.outline[revision][part]:
                self.outline[revision][part][chapter] = []
            if not section in self.outline[revision][part]:
                self.outline[revision][part][chapter].append(section)

    def _update_db_status(self, tc, reqt):
        if not reqt in self.db:
            raise ValueError("TC %s Reqt %s not found in database" % (tc, reqt))
        if self.db[reqt].status == "Relevant":
            self.db[reqt].status = "Tested"

    def check_reqt_coverage(self):
        if self.tc_d_and_r_filepath != '' and self.tc_d_r_rd_filepath == '':
            self.tc_d_and_r = TestCaseDescrAndReqts(self.tc_d_and_r_filepath)
            for testname in self.tc_d_and_r.tc_d_and_r:
                for reqt in self.tc_d_and_r.tc_d_and_r[testname].reqts:
                    self._update_db_status(testname, reqt)
        else:
            for testname in self.tc_d_r_rd.keys():
                for reqt in self.tc_d_r_rd[testname].reqt_list.keys():
                    self._update_db_status(testname, reqt)

    def generate_tc_d_r_rd(self, tc_d_and_r, reqts_db):

        for tc in sorted(self.tc_d_and_r.tc_d_and_r.keys()):
            descr = self.tc_d_and_r.tc_d_and_r[tc].descr
            for reqt in sorted(self.tc_d_and_r.tc_d_and_r[tc].reqts):
                if not reqt in self.db:
                    raise ValueError("TC %s Reqt %s not found in database"
                              % (tc, reqt))
                reqt_descr = self.db[reqt].descr
                if tc not in self.tc_d_r_rd:
                    self.tc_d_r_rd[tc] = DescrReqtReqtDescr(descr, reqt,
                                                            reqt_descr)
                    continue
                self.tc_d_r_rd[tc].reqt_list[reqt] = reqt_descr

def create_parser():
    parser = OptionParser(description="Create or check testcase/description/requirement/requirement description file.")
    parser.add_option('-m', '--d_and_r',
            dest = 'd_and_r_filepath',
            action = 'store', type = 'string',
            default = '',
            help = 'Testcase description and requirements file',
            metavar = 'FILE')
    parser.add_option('-d', '--database',
            dest = 'database_filepath',
            action = 'store', type = 'string',
            default = '',
            help = 'Checklist database file.',
            metavar = 'FILE')
    parser.add_option('-x', '--tc_descr_reqts_rd',
            dest = 'tc_d_r_rd',
            action = 'store', type = 'string',
            default = '',
            help = 'Testcase description, requirement, requirement description file created by this program.',
            metavar = 'FILE')
    parser.add_option('-c', '--check_outline',
            dest = 'outline',
            action = 'store', type = 'string',
            default = '',
            help = 'Check that all database requirements for the sections of the outline are covered by the d_and_r or tc_d_r_rd file',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if options.d_and_r_filepath != '':
        if not os.path.isfile(options.d_and_r_filepath):
            raise ValueError("Checklist file '%s' does not exist." %
                             options.checklist_filepath)
    if options.database_filepath != '':
        if not os.path.isfile(options.database_filepath):
            raise ValueError("Database file '%s' does not exist." %
                             options.database_filepath)
    if options.tc_d_r_rd != '':
        if not os.path.isfile(options.tc_d_r_rd):
            raise ValueError("TC_D_R_RD file '%s' does not exist." %
                             options.tc_d_r_rd)
    if options.outline != '':
        if not os.path.isfile(options.outline):
            raise ValueError("Outline file '%s' does not exist." %
                             options.outline)
        if options.database_filepath == '':
            raise ValueError("Must enter database file with outline.")
        if options.tc_d_r_rd == '' and options.d_and_r_filepath == '':
            raise ValueError("Must enter tc_d_r_rd or d_and_r file with outline.")

    if options.tc_d_r_rd != '':
        return

    if options.database_filepath == '' or options.d_and_r_filepath == '':
        raise ValueError("Must enter both database and d_and_r files...")

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

    tc_d_r_rd = TC_D_R_RD(options.tc_d_r_rd, options.d_and_r_filepath,
                          options.outline, options.database_filepath)
    if options.outline != '':
        tc_d_r_rd.check_reqt_coverage()
        print("MISSING:")
        tc_d_r_rd.print_missing_reqts()
        return
        
    if options.tc_d_r_rd == '':
        tc_d_r_rd.generate_tc_d_r_rd(
                               options.d_and_r_filepath,
                               options.database_filepath)
    tc_d_r_rd.write_tc_d_r_rd()

if __name__ == '__main__':
    sys.exit(main())
