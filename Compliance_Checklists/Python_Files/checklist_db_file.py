#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Support for the checklist database, which provides consistent references to
    all requirements and the merged_sorted_checklist.txt file evolves.
"""

from optparse import OptionParser
from collections import OrderedDict
import operator
import re
import sys
import os
import logging
import copy
from constants import *
from create_translation import *
from make_spreadsheet import ExcelEditor

class ComplianceDBFile(object):
    DATABASE_HEADER = "Sentence, Sentence_num, Reference, Type, Revision, Part, Chapter, Section, FileName, Table_Name, Checklist_ID, Optional"
    COMPLIANCE_HEADER = "Reference, Sentence, Type, Optional, Part, Section"
    def __init__(self, database = "", xl = ""):
        self.database_filepath = database
        self.xl = ExcelEditor('', xl)
        self.xl.text_filepath = xl

        self.db = {}
        self.db_revs = []
        if self.database_filepath != "":
            self.read_database()

    def read_database(self):
        logging.critical("Reading database file '%s'."
                      % self.database_filepath)
        try:
            db_file = open(self.database_filepath)
            db_lines = [line.strip() for line in db_file.readlines()]
            db_file.close()
        except:
            logging.critical("Failed reading database file '%s', continuing..."
                             % self.database_filepath)
            return

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
            rev = copy.deepcopy(toks[TOK_IDX_DB_H_REVISION])
            part = copy.deepcopy(toks[TOK_IDX_DB_H_PART])
            chap = copy.deepcopy(toks[TOK_IDX_DB_H_CHAPTER])
            sect = copy.deepcopy(toks[TOK_IDX_DB_H_SECTION])
            sent_num = copy.deepcopy(toks[TOK_IDX_DB_H_SENTENCE_NUM])
            if not sent_num.isdigit():
                raise ValueError("%s DB Line %d Invalid Sentence Number '%s'"
                           % (self.checklist_filepath, line_num+1, sent_num))
            if rev not in self.db:
                self.db[rev] = {part:{}}
            if part not in self.db[rev]:
                self.db[rev][part] = {chap:{}}
            if chap not in self.db[rev][part]:
                self.db[rev][part][chap] = {sect:{}}
            if sect not in self.db[rev][part][chap]:
                self.db[rev][part][chap][sect] = {sect:{}}
            if sent_num in self.db[rev][part][chap][sect]:
                raise ValueError("%s DB Line %d Duplicate Sentence Number '%s'"
                           % (self.checklist_filepath, line_num+1, sent_num))
            list_to_add = copy.deepcopy(toks[0:DATABASE_HEADER_TOKEN_COUNT])
            list_to_add.append(OrderedDict())
            for i, s_rev in enumerate(self.db_revs):
                first_tok_idx = (TOK_IDX_DB_H_FIRST_REV +
                                 (i * TOK_IDX_DB_H_TOK_COUNT))
                last_tok_idx = (TOK_IDX_DB_H_FIRST_REV +
                                ((i + 1) * TOK_IDX_DB_H_TOK_COUNT))
                list_to_add[DATABASE_HEADER_TOKEN_COUNT][s_rev] = (
                    copy.deepcopy(toks[first_tok_idx:last_tok_idx]))
            logging.info("DB %d: %s" % (line_num+2, list_to_add))
            if not sent_num.isdigit():
                raise ValueError("%s DB Line %d Invalid Sentence Number '%s'"
                           % (self.checklist_filepath, line_num+1, sent_num))
            temp = copy.deepcopy(list_to_add)
            self.db[rev][part][chap][sect][sent_num] = []
            self.db[rev][part][chap][sect][sent_num].extend(copy.deepcopy(list_to_add))

    def get_uid(self, rev, part, sect, sent_num):
        # Parts have the format "Part <part_num>: <Part Title>"
        # UID uses the <part_num>
        part_toks = [tok.strip() for tok in part.split(" ")]
        part_idx = part_toks.index("Part")
        part_num = part_toks[part_idx + 1][0:-1]

        # Sections have the format "<section_number> <section_title>"
        # UID uses <section_number>
        sec_toks = [tok.strip() for tok in sect.split(" ")]
        sec_num = sec_toks[0]
        num = int(sent_num)
        if (num < REQT_NUM_OFFSET_CHKLIST):
            reqt_type = 'r'
        elif (num < REQT_NUM_OFFSET_MANUAL):
            num = num - REQT_NUM_OFFSET_CHKLIST
            reqt_type = 'c'
        else:
            num = num - REQT_NUM_OFFSET_MANUAL
            reqt_type = 'm'

        uid = "R%sp%ss%s%s%04.0d" % (rev, part_num, sec_num, reqt_type, num)
        logging.info("UID: %s" % uid)
        return uid

    def update_keys(self, rev, part, chap, sect):
        if rev not in self.db:
            self.db[rev] = {}
        if rev not in self.db_revs:
            self.db_revs.append(rev)
        if part not in self.db[rev]:
            self.db[rev][part] = {}
        if chap not in self.db[rev][part]:
            self.db[rev][part][chap] = {}
        if sect not in self.db[rev][part][chap]:
            self.db[rev][part][chap][sect] = {}

    def add_db_item(self, rev, part, chap, sect, chk_sent_num, db_sent_num, toks, first_rev):
        uid = self.get_uid(rev,part,sect,db_sent_num)
        db_item = [uid]
        db_item.extend(toks)
        db_item.extend(["ACTIVE"])
        db_item.append(first_rev)
        self.db[rev][part][chap][sect][db_sent_num] = copy.deepcopy(db_item)
        logging.info("DB ADD: %s" % db_item)

    def write_database(self):
        print ("%s%s" %
               (MERGED_CHECKLIST_SORTED_SPEC_REVS, " ".join(self.db_revs)))
        h = DATABASE_HEADER
        for rev in self.db_revs:
            h = (CHECKLIST_HEADER_REV_FORMAT % (h, rev, rev, rev, rev))
        print ("%s" % h)
        if self.db == {}:
            print("Nothing in sorted checklist.")

        for rev in self.db_revs:
            for part in sorted(self.db[rev]):
                for chap in sorted(self.db[rev][part]):
                    for sect in sorted(self.db[rev][part][chap]):
                        for sent_num in sorted(self.db[rev][part][chap][sect]):
                            if not sent_num.isdigit():
                                logging.info("Invalid Database Sentence Number '%s'" % [rev,part,chap,sect,sent_num])
                                continue
                            entry = self.db[rev][part][chap][sect][sent_num]
                            stuff = entry[TOK_IDX_DB_H_CONST_REF:DATABASE_HEADER_TOKEN_COUNT]
                            line = "'%s'" % "', '".join(stuff)
                            for e_rev in entry[TOK_IDX_DB_H_FIRST_REV]:
                                rev_entry = entry[TOK_IDX_DB_H_FIRST_REV][e_rev]
                                line = "%s, '%s'" % (line, "', '".join(rev_entry))
                            print("%s" % line)

    def extract_part_number(self, part_header):
        toks = [tok.strip() for tok in part_header.split(" ")]
        num = ""
        for tok_i, tok in enumerate(toks):
            if tok == "Part":
                num = toks[tok_i + 1]
                break
        if num == "":
            raise ValueError("Could not find part number in '%s'" % part_header)
        num = num.replace(":", "").strip()
        return "Part " + str(int(num))

    def extract_section_number(self, part_header):
        return [tok.strip() for tok in part_header.split(" ")][0]

    def write_compliance_checklist(self, target_rev):
        if not target_rev in self.db_revs:
            raise ValueError("Revision %s not found in database %s" % (rev, self.database_filepath))
        print(self.COMPLIANCE_HEADER)
        self.xl.header = [tok.strip() for tok in self.COMPLIANCE_HEADER.split(",")]
        for rev in self.db_revs:
            if rev > target_rev:
                continue
            for part in sorted(self.db[rev]):
                for chap in sorted(self.db[rev][part]):
                    for sect in sorted(self.db[rev][part][chap]):
                        for sent_num in sorted(self.db[rev][part][chap][sect]):
                            entry = self.db[rev][part][chap][sect][sent_num]
                            logging.info('Entry: %s' % str(entry))
                            if entry == {}:
                                continue
                            # If the requirement is for a later specification revision, skip it.
                            if entry[TOK_IDX_DB_H_REVISION] > target_rev:
                                continue
                            if entry[TOK_IDX_DB_H_FIRST_REV][target_rev] == ['', '', '', '']:
                                continue
                            # Create the entry
                            stuff = entry[TOK_IDX_DB_H_FIRST_REV][rev]
                            part_no = self.extract_part_number(stuff[TOK_IDX_DB_H_FIRST_PART - TOK_IDX_DB_H_FIRST_REV])
                            secn_no = self.extract_section_number(stuff[TOK_IDX_DB_H_FIRST_SECN - TOK_IDX_DB_H_FIRST_REV])
                            optional = ""
                            if entry[TOK_IDX_DB_H_OPTIONAL] == "OPTIONAL":
                                optional = "OPTIONAL"

                            toks = [entry[TOK_IDX_DB_H_CONST_REF],
                                    entry[TOK_IDX_DB_H_SENTENCE],
                                    entry[TOK_IDX_DB_H_TYPE],
                                    optional,
                                    part_no,
                                    secn_no]
                            self.xl.data.append(toks)
                            print("'%s'" % "', '".join(toks))

    def create_excel(self, target_rev, xl_filepath):
        self.xl._create_excel()
        self.xl._format_excel()
        self.xl.write_excel()

def create_parser():
    parser = OptionParser(description="Update checklist database file based on new merged_sorted_checklist.txt.")
    parser.add_option('-d', '--database',
            dest = 'database_filepath',
            action = 'store', type = 'string',
            default = 'Historic_Checklists/checklist_db.txt',
            help = 'Checklist database file created by this program.',
            metavar = 'FILE')
    parser.add_option('-r', '--revision',
            dest = 'revision',
            action = 'store', type = 'string',
            default = 'NoRev',
            help = 'Compliance checklist revision to be printed.',
            metavar = 'FILE')
    parser.add_option('-x', '--excel',
            dest = 'xl_filepath',
            action = 'store', type = 'string',
            default = 'NoRev',
            help = 'Compliance checklist revision to be printed.',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if not os.path.isfile(options.database_filepath):
        raise ValueError("Database file '%s' does not exist." %
                         options.database_filepath)

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

    db = ComplianceDBFile(options.database_filepath, options.xl_filepath)
    if options.revision == "NoRev":
        db.write_database()
        return

    db.write_compliance_checklist(options.revision)
    if not options.xl_filepath == "":
        db.create_excel(options.revision, options.xl_filepath)

if __name__ == '__main__':
    sys.exit(main())
