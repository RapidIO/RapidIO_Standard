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
from constants import *
from create_translation import *

class ReqtDatabaseUpdater(object):
    DATABASE_HEADER = "Sentence, Sentence_num, Reference, Type, Revision, Part, Chapter, Section, FileName, Table_Name, Checklist_ID, Optional"
    def __init__(self, checklist, database):
        self.checklist_filepath = checklist
        self.database_filepath = database

        self.chk = {}
        self.db = {}
        self.db_revs = []
        self._read_checklist()
        self._read_database()

    def _read_checklist(self):
        logging.info("Reading merged sorted checklist file '%s'."
                      % self.checklist_filepath)
        chk_file = open(self.checklist_filepath)
        chk_lines = [line.strip() for line in chk_file.readlines()]
        chk_file.close()

        if not chk_lines[0].startswith(MERGED_CHECKLIST_SPEC_REVS):
            raise ValueError("Checklist line 0 does not start with '%s'." %
                          MERGED_CHECKLIST_SPEC_REVS)

        if not chk_lines[1].startswith(MERGED_CHECKLIST_SORTED_SPEC_REVS):
            raise ValueError("Checklist line 1 does not start with '%s'." %
                          MERGED_CHECKLIST_SORTED_SPEC_REVS)
        self.chk_revs = [item.strip() for item in
             chk_lines[1][len(MERGED_CHECKLIST_SORTED_SPEC_REVS):].split(" ")]
        logging.info("Checklist file revs: %s" % ",".join(self.chk_revs))

        if not chk_lines[2].startswith(CHECKLIST_HEADER):
            raise ValueError("Checklist line 2 does not start with '%s'." %
                          CHECKLIST_HEADER)

        for line_num, line in enumerate(chk_lines[3:]):
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            if len(toks) < TOK_IDX_MRG_CHK_H_MIN_TOK_COUNT:
                raise ValueError("%s %d Line %s tok len %d"
                              % (reqt, line_num+1, line, len(toks)))
            rev = toks[TOK_IDX_CHK_H_REVISION]
            part = toks[TOK_IDX_CHK_H_PART]
            chap = toks[TOK_IDX_CHK_H_CHAPTER]
            sect = toks[TOK_IDX_CHK_H_SECTION]
            sent_num = toks[TOK_IDX_CHK_H_SENTENCE_NUM]
            if rev not in self.chk:
	        self.chk[rev] = {part:{}}
            if part not in self.chk[rev]:
                self.chk[rev][part] = {chap:{}}
            if chap not in self.chk[rev][part]:
                self.chk[rev][part][chap] = {sect:{}}
            if sect not in self.chk[rev][part][chap]:
                self.chk[rev][part][chap][sect] = {sect:{}}
            if sent_num in self.chk[rev][part][chap][sect]:
                raise ValueError("%s Line %d Duplicate Sentence Number '%s'"
                           % (self.checklist_filepath, line_num+1, sent_num))
            list_to_add = toks[0:CHECKLIST_HEADER_TOKEN_COUNT]
            list_to_add.append({})
            print("Line %d %s" % (line_num, "\n".join(toks)))
            for i, s_rev in enumerate(self.chk_revs):
                first_tok_idx = (TOK_IDX_MRG_CHK_H_FIRST_REV +
                                 (i * TOK_IDX_MRG_CHK_H_TOK_COUNT))
                last_tok_idx = (TOK_IDX_MRG_CHK_H_FIRST_REV +
                                ((i + 1) * TOK_IDX_MRG_CHK_H_TOK_COUNT))
                print("F:L %d:%d" % (first_tok_idx, last_tok_idx))
                list_to_add[CHECKLIST_HEADER_TOKEN_COUNT][s_rev] = (
                    toks[first_tok_idx:last_tok_idx])
            self.chk[rev][part][chap][sect][sent_num] = copy.deepcopy(list_to_add);
            
    def _read_database(self):
        logging.info("Reading database file '%s'."
                      % self.database_filepath)
        try:
            db_file = open(self.database_filepath)
            db_lines = [line.strip() for line in db_file.readlines()]
            db_file.close()
        except:
            return

        if not db_lines[0].startswith(MERGED_CHECKLIST_SORTED_SPEC_REVS):
            raise ValueError("Database line 0 does not start with '%s'." %
                          MERGED_CHECKLIST_SORTED_SPEC_REVS)
        self.db_revs = [item.strip() for item in
             db_lines[0][len(MERGED_CHECKLIST_SORTED_SPEC_REVS),].split(" ")]
        logging.info("Database file revs: %s" % ",".join(self.db_revs))

        if not db_lines[1].startswith(DATABASE_HEADER):
            raise ValueError("Database line 1 does not start with '%s'." %
                          DATABASE_HEADER)

        for line_num, line in enumerate(db_lines[2:]):
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            if not len(toks) >= TOK_IDX_DB_H_FIRST_SECN:
                raise ValueError("%s %d Line %s tok len %d"
                              % (reqt, line_num+1, line, len(toks)))
            rev = toks[TOK_IDX_DB_H_REVISION]
            part = toks[TOK_IDX_DB_H_PART]
            chap = toks[TOK_IDX_DB_H_CHAPTER]
            sect = toks[TOK_IDX_DB_H_SECTION]
            sent_num = toks[TOK_IDX_DB_H_SENTENCE_NUM]
            if rev not in self.db:
	        self.db[rev] = {part:{}}
            if part not in self.db[rev]:
                self.db[rev][part] = {chap:{}}
            if chap not in self.db[rev][part]:
                self.db[rev][part][chap] = {sect:{}}
            if sect not in self.db[rev][part][chap]:
                self.db[rev][part][chap][sect] = {sect:{}}
            if sent_num in self.db[rev][part][chap][sect]:
                raise ValueError("%s Line %d Duplicate Sentence Number '%s'"
                           % (self.checklist_filepath, line_num+1, sent_num))
            list_to_add = toks[0:TOK_IDX_DB_H_OPTIONAL]
            list_to_add.append({})
            for i, s_rev in enumerate(self.db_revs):
                first_tok_itx = (TOK_IDX_DB_H_FIRST_REV +
                                 (i * TOK_IDX_MRG_DB_H_TOK_COUNT))
                last_tok_itx = (TOK_IDX_DB_H_FIRST_REV +
                                ((i + 1) * TOK_IDX_MRG_DB_H_TOK_COUNT) - 1)
                list_to_append[DATABASE_HEADER_TOKEN_COUNT][s_rev] = (
                    toks[first_tok_idx:last_tok_idx])
            self.db[rev][part][chap][sect][sent_num] = copy.deepcopy(list_to_add);

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
        print("UID: %s" % uid)
        return uid

    def update_database(self):
        for rev in self.chk_revs:
            if rev not in self.db:
                self.db[rev] = {}
            if rev not in self.db_revs:
                self.db_revs.append(rev)
            for part in self.chk[rev]:
                if part not in self.db[rev]:
                    self.db[rev][part] = {}
                for chap in self.chk[rev][part]:
                    if chap not in self.db[rev][part]:
                        self.db[rev][part][chap] = {}
                    for sect in self.chk[rev][part][chap]:
                        if sect not in self.db[rev][part][chap]:
                            self.db[rev][part][chap][sect] = {}
                        for sent_num in self.chk[rev][part][chap][sect]:
                            if sent_num not in self.db[rev][part][chap]:
                                item = self.chk[rev][part][chap][sect][sent_num]
                                uid = self.get_uid(rev,part,sect,sent_num)
                                db_item = [uid]
                                db_item.extend(item[TOK_IDX_CHK_H_SENTENCE:
                                                  CHECKLIST_HEADER_TOKEN_COUNT])
                                db_item.extend(["ACTIVE"])
                                db_item.extend([item[TOK_IDX_MRG_CHK_H_FIRST_REV]])
                                self.db[rev][part][chap][sect][sent_num] = db_item
                                for item_idx, item in enumerate(db_item):
                                    print(item_idx, item)
                            
    def write_database(self):
        print ("%s%s" %
               (MERGED_CHECKLIST_SORTED_SPEC_REVS, " ".join(self.db_revs)))
        h = DATABASE_HEADER
        for rev in self.db_revs:
            h = (CHECKLIST_HEADER_REV_FORMAT % (h, rev, rev, rev, rev))
        print ("%s" % h)
        if self.db == {}:
            print "Nothing in sorted checklist."

        for rev in self.db_revs:
            for part in self.db[rev]:
                for chap in self.db[rev][part]:
                    for sect in self.db[rev][part][chap]:
                        for sent_num in self.db[rev][part][chap][sect]:
                            entry = self.db[rev][part][chap][sect][sent_num]
                            consts = entry[TOK_IDX_DB_H_CONST_REF:TOK_IDX_DB_H_STATUS]
                            line = "'%s'" % "', '".join(consts)
                            for e_rev in entry[TOK_IDX_DB_H_FIRST_REV]:
                                rev_entry = entry[TOK_IDX_DB_H_FIRST_REV][e_rev]
                                line = "%s, '%s'" % (line, "', '".join(rev_entry))
                            print ("%s" % line)

def create_parser():
    parser = OptionParser(description="Update checklist database file based on new merged_sorted_checklist.txt.")
    parser.add_option('-c', '--checklist',
            dest = 'checklist_filepath',
            action = 'store', type = 'string',
            default = 'Historic_Checklists/merged_sorted_checklist.txt',
            help = 'Merged checklist file created by merge_checklists.py',
            metavar = 'FILE')
    parser.add_option('-d', '--database',
            dest = 'database_filepath',
            action = 'store', type = 'string',
            default = 'Historic_Checklists/checklist_db.txt',
            help = 'Checklist database file created by this program.',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if not os.path.isfile(options.checklist_filepath):
        raise ValueError("Checklist file '%s' does not exist." %
                         options.checklist_filepath)

def main(argv = None):
    logging.basicConfig(level=logging.WARN)
    parser = create_parser()
    if argv is None:
        argv = sys.argv[1:]

    (options, argv) = parser.parse_args(argv)
    if len(argv) != 0:
        print 'Invalid argument!'
        print
        parser.print_help()
        return -1

    try:
        validate_options(options)
    except ValueError as e:
        print e
        sys.exit(-1)

    updater = ReqtDatabaseUpdater(options.checklist_filepath,
                             options.database_filepath)
    updater.update_database()
    updater.write_database()

if __name__ == '__main__':
    sys.exit(main())
