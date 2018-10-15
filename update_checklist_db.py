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

    def _read_database(self):
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
                raise ValueError("%s %d DB Line %s tok len %d"
                              % (reqt, line_num+1, line, len(toks)))
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

    def _update_db_item(self, rev, part, chap, sect, sent_num):
        chk_item = self.chk[rev][part][chap][sect][sent_num]
        sent_num_val = int(sent_num)
        sn_keys = sorted(self.db[rev][part][chap][sect].keys())

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
                if (   self.db[rev][part][chap][sect][srch_sent_num][TOK_IDX_DB_H_SENTENCE]
                   == chk_item[TOK_IDX_CHK_H_SENTENCE]):
                    self.db[rev][part][chap][sect][srch_sent_num][TOK_IDX_DB_H_STATUS] = "ACTIVE"
                    logging.debug("Update REQT %s DB %s" % ([rev, part, chap, sect, sent_num], srch_sent_num))
                    logging.debug("Update REQT CHK item %s" % chk_item)
                    logging.debug("Update REQT DB  item %s" % self.db[rev][part][chap][sect][srch_sent_num])
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
                temp_db_item = self.db[rev][part][chap][sect][srch_sent_num]
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
                logging.debug("Update CHK DB  item %s" % self.db[rev][part][chap][sect][srch_sent_num])
                self.db[rev][part][chap][sect][srch_sent_num][TOK_IDX_DB_H_STATUS] = "ACTIVE"
                self.db[rev][part][chap][sect][srch_sent_num][TOK_IDX_DB_H_SENTENCE] = chk_item[TOK_IDX_CHK_H_SENTENCE]
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
                self.db[rev][part][chap][sect][sent_num][TOK_IDX_DB_H_STATUS] = "ACTIVE"
                self.db[rev][part][chap][sect][sent_num][TOK_IDX_DB_H_SENTENCE] = chk_item[TOK_IDX_CHK_H_SENTENCE]
                return True

            ## Manual item does not exist in the database.
            ## Add the item.
            return False

        raise ValueError("Update bad checklist sentence number: %s" %
            [rev, part, chap, sect, sent_num])

    def _add_db_item(self, rev, part, chap, sect, chk_sent_num, db_sent_num):
        item = self.chk[rev][part][chap][sect][chk_sent_num]
        uid = self.get_uid(rev,part,sect,db_sent_num)
        db_item = [uid]
        db_item.extend(item[TOK_IDX_CHK_H_SENTENCE:CHECKLIST_HEADER_TOKEN_COUNT])
        db_item.extend(["ACTIVE"])
        db_item.extend([item[TOK_IDX_MRG_CHK_H_FIRST_REV]])
        self.db[rev][part][chap][sect][db_sent_num] = copy.deepcopy(db_item)
        logging.info("DB ADD: %s" % item)

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
                        logging.info("Keys: %s" % self.chk[rev][part][chap][sect].keys())
                        found_one = False
                        for sent_num in self.chk[rev][part][chap][sect]:
                            if not sent_num.isdigit():
                                logging.info("Invalid Checklist Sentence Number '%s'" % [rev, part, chap, sect, sent_num, self.chk[rev][part][chap][sect].keys()])
                                found_one = True
                                continue
                            if not self._update_db_item(rev, part, chap, sect, sent_num):
                                self._add_db_item(rev, part, chap, sect, sent_num, sent_num)
                        if not found_one:
                            logging.info("ALL VALID Checklist Sentence Numbers '%s'" % [rev, part, chap, sect, self.chk[rev][part][chap][sect].keys()])

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
