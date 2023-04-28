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
from checklist_db_file import ComplianceDBFile

class ReqtDatabaseUpdater(object):
    def __init__(self, checklist, database):
        self.checklist_filepath = checklist
        self.database_filepath = database

        self.chk = {}
        self.db = ComplianceDBFile(database)
        self.read_checklist()

    def read_checklist(self):
        logging.critical("Reading merged sorted checklist file '%s'."
                      % self.checklist_filepath)
        with open(self.checklist_filepath, 'r') as chk_file:
            chk_lines = [line.strip() for line in chk_file.readlines()]

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
            logging.info("Tokens: %s" % toks)
            rev = copy.deepcopy(toks[TOK_IDX_CHK_H_REVISION])
            part = copy.deepcopy(toks[TOK_IDX_CHK_H_PART])
            chap = copy.deepcopy(toks[TOK_IDX_CHK_H_CHAPTER])
            sect = copy.deepcopy(toks[TOK_IDX_CHK_H_SECTION])
            sent_num = copy.deepcopy(toks[TOK_IDX_CHK_H_SENTENCE_NUM])
            logging.info("Sentence Num: %s" % sent_num)
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
            list_to_add.append(OrderedDict())
            for i, s_rev in enumerate(self.chk_revs):
                first_tok_idx = (TOK_IDX_MRG_CHK_H_FIRST_REV +
                                 (i * TOK_IDX_MRG_CHK_H_TOK_COUNT))
                last_tok_idx = (TOK_IDX_MRG_CHK_H_FIRST_REV +
                                ((i + 1) * TOK_IDX_MRG_CHK_H_TOK_COUNT))
                logging.info("F:L %d:%d" % (first_tok_idx, last_tok_idx))
                list_to_add[CHECKLIST_HEADER_TOKEN_COUNT][s_rev] = copy.deepcopy(
                    toks[first_tok_idx:last_tok_idx])
            logging.info("Sentence Num: %s" % sent_num)
            temp = copy.deepcopy(list_to_add)
            self.chk[rev][part][chap][sect][sent_num] = []
            self.chk[rev][part][chap][sect][sent_num].extend(temp)
            logging.info("Sentence Num: %s" % sent_num)

    def update_db_item(self, rev, part, chap, sect, sent_num):
        chk_item = self.chk[rev][part][chap][sect][sent_num]
        sent_num_val = int(sent_num)
        sn_keys = sorted(self.db.db[rev][part][chap][sect].keys())

        for i, k in enumerate(sn_keys):
            if not k.isdigit():
                sn_keys.remove(k)

        if REQT_NUM_OFFSET_NONE <= sent_num_val <= REQT_NUM_OFFSET_SPEC_MAX:
            ## Requirement extracted from a standard.
            ## See if the sentence exists in this section,
            ## and mark that requirement as "ACTIVE"
            for srch_sent_num in sn_keys:
                ## Only search other requirements extracted from the standard,
                ## or that were automatically numbered...
                if (not ((REQT_NUM_OFFSET_NONE <= int(srch_sent_num) <= REQT_NUM_OFFSET_SPEC_MAX)
                        or
                         (REQT_NUM_OFFSET_AUTO <= int(srch_sent_num)))):
                    continue
                if (   self.db.db[rev][part][chap][sect][srch_sent_num][TOK_IDX_DB_H_SENTENCE]
                   == chk_item[TOK_IDX_CHK_H_SENTENCE]):
                    self.db.db[rev][part][chap][sect][srch_sent_num][TOK_IDX_DB_H_STATUS] = "ACTIVE"
                    logging.debug("Update REQT %s DB %s" % ([rev, part, chap, sect, sent_num], srch_sent_num))
                    logging.debug("Update REQT CHK item %s" % chk_item)
                    logging.debug("Update REQT DB  item %s" % self.db.db[rev][part][chap][sect][srch_sent_num])
                    return True

            ## The sentence has changed.
            ## Create a new requirement.
            if sent_num in sn_keys:
                ## The sentence number exists.  The implication
                ## is that the requirement has changed or the numbering
                ## for a previously extracted requirement has changed.
                ## Create a new requirement reference.
                new_sent_num = max(max(sn_keys), str(REQT_NUM_OFFSET_AUTO))
                if new_sent_num != str(REQT_NUM_OFFSET_AUTO):
                    new_sent_num = str(int(new_sent_num) + 1)
                logging.warning("ADD REQT NEW %s DB %s" % ([rev, part, chap, sect, sent_num], new_sent_num))
                self._add_db_item(rev, part, chap, sect, sent_num, new_sent_num)
                return True
            ## The sentence number does exist.
            ## Add the requirement.
            logging.warning("ADD REQT FALSE")
            return False

        if REQT_NUM_OFFSET_CHKLIST <= sent_num_val <= REQT_NUM_OFFSET_CHKLIST_MAX:
            ## Requirement extracted from a checklist.
            ## Checklist sentence numbers are automatically generated,
            ## and so may vary with the checklist parsing.
            ##
            ## Identify the requirement in the database using
            ## the file, table title, and table reference, then
            ## update the sentence and status of the item.

            for srch_sent_num in sn_keys:
                temp_db_item = self.db.db[rev][part][chap][sect][srch_sent_num]
                if temp_db_item[TOK_IDX_DB_H_FILENAME] == '':
                    continue
                if (temp_db_item[TOK_IDX_DB_H_FILENAME]
                   != chk_item[TOK_IDX_CHK_H_FILENAME]):
                    continue
                if (temp_db_item[TOK_IDX_DB_H_TABLE_NAME]
                   != chk_item[TOK_IDX_CHK_H_TABLE_NAME]):
                    continue
                if (temp_db_item[TOK_IDX_DB_H_CHECKLIST_ID]
                   != chk_item[TOK_IDX_CHK_H_CHECKLIST_ID]):
                    continue
                logging.debug("Update CHK %s DB %s" % ([rev, part, chap, sect, sent_num], srch_sent_num))
                logging.debug("Update CHK CHK item %s" % chk_item)
                logging.debug("Update CHK DB  item %s" % self.db.db[rev][part][chap][sect][srch_sent_num])
                self.db.db[rev][part][chap][sect][srch_sent_num][TOK_IDX_DB_H_STATUS] = "ACTIVE"
                self.db.db[rev][part][chap][sect][srch_sent_num][TOK_IDX_DB_H_SENTENCE] = chk_item[TOK_IDX_CHK_H_SENTENCE]
                self.db.db[rev][part][chap][sect][srch_sent_num][TOK_IDX_DB_H_OPTIONAL] = chk_item[TOK_IDX_CHK_H_OPTIONAL]
                return True

            ## Did not find that file/table/reference in this section.
            ## Must be a new requirement in the checklist.
            if sent_num in sn_keys:
                ## Sentence number has already been used for a different
                ## requirement.  Manufacture a unique sentence number
                ## in the checklist range for this checklist item.
                new_sent_num = max([key for key in sn_keys if (REQT_NUM_OFFSET_CHKLIST <= int(key) <= REQT_NUM_OFFSET_CHKLIST_MAX)])
                new_sent_num = str(int(new_sent_num) + 1)
                if int(new_sent_num) >= REQT_NUM_OFFSET_MANUAL:
                    raise ValueError("Out of numbers: %s" % [rev, part, chap, sect, sent_num])
                logging.warning("ADD CHK NEW %s DB %s" % ([rev, part, chap, sect, sent_num], new_sent_num))
                self._add_db_item(rev, part, chap, sect, sent_num, new_sent_num)
                return True

            ## Sentence number has not been used previously, so just add
            ## the requirement.
            logging.info("ADD CHK FALSE")
            return False

        if REQT_NUM_OFFSET_MANUAL <= sent_num_val <= REQT_NUM_OFFSET_MANUAL_MAX:
            ## Sentence number for a manually managed item.
            ## The sentence number cannot change.
            ##
            ## If the item exists in the database, update the
            ## item and call it done.
            if sent_num in sn_keys:
                self.db.db[rev][part][chap][sect][sent_num][TOK_IDX_DB_H_STATUS] = "ACTIVE"
                self.db.db[rev][part][chap][sect][sent_num][TOK_IDX_DB_H_SENTENCE] = chk_item[TOK_IDX_CHK_H_SENTENCE]
                return True

            ## Manual item does not exist in the database.
            ## Add the item.
            return False

        raise ValueError("Update bad checklist sentence number: %s" %
            [rev, part, chap, sect, sent_num])

    def update_database(self):
        for rev in self.chk_revs:
            for part in self.chk[rev]:
                for chap in self.chk[rev][part]:
                    for sect in self.chk[rev][part][chap]:
                        logging.info("Keys: %s" % self.chk[rev][part][chap][sect].keys())
                        self.db.update_keys(rev, part, chap, sect)
                        found_one = False
                        for sent_num in self.chk[rev][part][chap][sect]:
                            if not sent_num.isdigit():
                                logging.info("Invalid Checklist Sentence Number '%s'" % [rev, part, chap, sect, sent_num, self.chk[rev][part][chap][sect].keys()])
                                found_one = True
                                continue
                            if not self.update_db_item(rev, part, chap, sect, sent_num):
                                temp = self.chk[rev][part][chap][sect][sent_num]
                                temp_items = temp[TOK_IDX_CHK_H_SENTENCE:CHECKLIST_HEADER_TOKEN_COUNT]
                                first_rev = temp[TOK_IDX_MRG_CHK_H_FIRST_REV]
                                self.db.add_db_item(rev, part, chap, sect, sent_num, sent_num, temp_items, first_rev)
                        if not found_one:
                            logging.info("ALL VALID Checklist Sentence Numbers '%s'" % [rev, part, chap, sect, self.chk[rev][part][chap][sect].keys()])

    def write_database(self):
        self.db.write_database()

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
        print('Invalid argument!')
        print
        parser.print_help()
        return -1

    try:
        validate_options(options)
    except ValueError as e:
        print(e)
        sys.exit(-1)

    updater = ReqtDatabaseUpdater(options.checklist_filepath,
                             options.database_filepath)
    logging.critical("Updating database.")
    updater.update_database()
    logging.critical("Writing updated database to stdout.")
    updater.write_database()

if __name__ == '__main__':
    sys.exit(main())
