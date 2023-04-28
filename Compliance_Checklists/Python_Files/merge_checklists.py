#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Merge the checklists, updating references from the outlines provided.

    - Merge the "checklist" files generated by parse_checklist.py
    - Sort by specification revision, chapter, and section
    - Output for each checklist item:
      - statement/sentence that defines the checklist item
      - type (REQUIREMENT/RECOMMENDATION)
      - Array of specification references, where each reference is:
        - Specification revision
        - Part name/number
        - Chapter number and heading
        - Section number and heading
"""

from optparse import OptionParser
from collections import OrderedDict
import operator
import re
import sys
import os
import logging
from constants import *
from create_translation import *

class ChecklistMerger(object):
    def __init__(self, checklists, outlines, translations, requirements, man_reqts, drop_reqts):
        self.checklists = checklists
        self.outlines = outlines
        self.requirements = requirements
        self.manual_requirements = man_reqts
        self.drop_requirements = drop_reqts
        self.merge = []
	self.drop_lines = []

        self._read_outlines()
        self._translator = RapidIOTranslationMerger(translations)
        self.header = CHECKLIST_HEADER

        self.trans_keys = self._translator.trans.keys()
        print ("%s%s" % (MERGED_CHECKLIST_SPEC_REVS,
                         " ".join(self.trans_keys)))
        self.trans_keys.sort()
        print ("%s%s" % (MERGED_CHECKLIST_SORTED_SPEC_REVS,
                         " ".join(self.trans_keys)))
        for t_rev in self.trans_keys:
            self.header = (CHECKLIST_HEADER_REV_FORMAT
                         % (self.header, t_rev, t_rev, t_rev, t_rev))
        self._read_requirements()
        self._read_checklists()

    def _add_outline_reference(self, revision, part_name, part_title,
                                               ch_name, ch_title,
                                               sec_num, sec_title):
        if revision not in self.outline_reference:
            self.outline_reference.update({revision:{}})
        if part_name not in self.outline_reference[revision]:
            self.outline_reference[revision].update({part_name: [part_title, {}]})
        if ch_name not in self.outline_reference[revision][part_name][1]:
            self.outline_reference[revision][part_name][1].update({ch_name: [ch_title, {}]})
        if sec_num not in self.outline_reference[revision][part_name][1][ch_name][1]:
            self.outline_reference[revision][part_name][1][ch_name][1].update({sec_num:sec_title})
        else:
            raise ValueError("Duplicate sections %s %s %s %s"
                           % (revision, part_name, ch_name, sec_num))

    def _read_outlines(self):
        self.outline_lines = []
        self.outline_reference = {}
        for outline_path in self.outlines:
            logging.info("Processing outline '%s'." % outline_path)
            outline_file = open(outline_path)
            lines = [line.strip() for line in outline_file.readlines()]
            outline_file.close()

            header_items = [item.strip() for item in OUTLINE_HEADER.split(",")]
            line_items = [item.strip() for item in lines[0][1:-1].split("', '")]
            if not header_items == line_items:
                raise ValueError("Bad format: File %s first line is %s not %s"
                             % (outline_path, line_items, header_items))

            tokenized_lines = []
            for x, line in enumerate(lines[1:]):
                line_num = x + 1
                tokenized_line = [re.sub("'", "", tok.strip()).strip() for tok in line.split("', ")]
                if not len(tokenized_line) == 4:
                    raise ValueError("Bad format: File %s line %d: %s"
                                 % (outline_path, line_num, tokenized_line))
                # Outline: revision, part, chapter, section
                logging.debug("%s: %d Outline: %s" % (outline_path, x, tokenized_line))
                self.outline_lines.append(tokenized_line)

                # Parts have the format "Part <part_num>: <Part Title>"
                # Checklist part references have the form "Part <part_num>"
                # Lines below should create a Checklist part_name from the outline
                part_toks = [tok.strip() for tok in tokenized_line[1].split(" ")]
                part_idx = part_toks.index("Part")
                part_name = " ".join(part_toks[part_idx:part_idx + 2])
                part_name = part_name[:-1]
                # Chapters have the format "Chapter <chapter_number> <Chapter_Title>"
                # Checklist chapter references have the form "Chapter <chapter_num>"
                # Lines below should create a Checklist chapter_name from the outline
                ch_toks = [tok.strip() for tok in tokenized_line[2].split(" ")]
                ch_name = " ".join(ch_toks[0:2])
                # Sections have the format "<section_number> <section_title>"
                # Checklist section references have the form "<section_num>"
                # Lines below should create a Checklist section_number from the outline
                sec_toks = [tok.strip() for tok in tokenized_line[3].split(" ")]
                sec_num = sec_toks[0]

                reference = [tokenized_line[0], part_name, ch_name, sec_num]
                self._add_outline_reference(tokenized_line[0], part_name, tokenized_line[1],
                                           ch_name, tokenized_line[2],
                                           sec_num, tokenized_line[3])
                logging.debug("%s: %d Ref: %s" % (outline_path, x, reference))

    def _read_requirements(self):
        for reqt in self.drop_requirements:
            logging.info("Processing DROP requirements file '%s'." % reqt)
            self._drop_requirements(reqt)
        for reqt in self.requirements:
            logging.info("Processing requirements file '%s'." % reqt)
            self._process_requirements(reqt, REQT_NUM_OFFSET_NONE)
        for reqt in self.manual_requirements:
            logging.info("Processing manual requirements file '%s'." % reqt)
            self._process_requirements(reqt, REQT_NUM_OFFSET_MANUAL)

    def _process_requirements(self, reqt, reqt_num_adj):
        reqt_file = open(reqt)
        reqt_lines = [line.strip() for line in reqt_file.readlines()]
        reqt_file.close()

        for line_num, line in enumerate(reqt_lines[1:]):
            #    0        1      2        3       4       5            6
            # Revision, Part, Chapter, Section, Type, Sentence_num, Sentence
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            if not len(toks) == REQUIREMENTS_HEADER_TOKEN_COUNT:
                raise ValueError("%s %d Line %s tok len %d"
                              % (reqt, line_num+1, line, len(toks)))
            del_line = [toks[0], toks[1], toks[2], toks[3], toks[4], toks[6]]
            if del_line in self.drop_lines:
                logging.info("Dropping requirement '%s'" % "', '".join(toks))
                continue

            # Checklist: Sentence, Sentence_Num, Type, Revision, Part,
            #             Chapter, Section, Checklist_FileName,
            #            Checklist_Table_Name, Checklist_ID,
            #            Optional, [rev/part/ch/sec] per translation
            line_2_merge = [toks[TOK_IDX_REQTS_SENTENCE],
                            str(int(toks[TOK_IDX_REQTS_REQT_NUM]) + reqt_num_adj),
                            toks[TOK_IDX_REQTS_TYPE],
                            toks[TOK_IDX_REQTS_REVISION],
                            toks[TOK_IDX_REQTS_PART],
                            toks[TOK_IDX_REQTS_CHAPTER],
                            toks[TOK_IDX_REQTS_SECTION],
                            reqt, "N/A", "N/A",
                            'REQUIREMENT']
            ref = [toks[TOK_IDX_REQTS_REVISION],
                   toks[TOK_IDX_REQTS_PART],
                   toks[TOK_IDX_REQTS_CHAPTER],
                   toks[TOK_IDX_REQTS_SECTION]]
            # The requirements are all from new sections.
            # Only translate forward, as it's not possible
            # to go backward.
            for t_key in self.trans_keys:
                if toks[0] not in self.trans_keys:
                    logging.warn("%s not in %s, line %s" % (toks[0], self.trans_keys, toks))
                    raise ValueError("%s not in %s, line %s" % (toks[0], self.trans_keys, toks))
                if t_key < toks[0]:
                    logging.debug("%s %s Extend with Nulls"
                               % (t_key,toks[0]))
                    line_2_merge.extend(['', '', '', ''])
                elif t_key > toks[0]:
                    t_rev, t_part, t_chap, t_sec = self._translator.translate(
                         toks[0], toks[1], toks[2], toks[3], t_key)
                    line_2_merge.extend([t_rev, t_part, t_chap, t_sec])
                    logging.debug("%s %s:%s Extend with translation"
                               % (t_key,toks[0], [t_rev, t_part, t_chap, t_sec]))
                else:
                    logging.debug("%s %s Extend with items"
                               % (t_key,[toks[0], toks[1], toks[2], toks[3]]))
                    line_2_merge.extend([toks[0], toks[1], toks[2], toks[3]])
            self.merge.append(line_2_merge)

    def _drop_requirements(self, reqt):
        drop_file = open(reqt)
        drop_lines = [line.strip() for line in drop_file.readlines()]
        drop_file.close()

        for line_num, line in enumerate(drop_lines[1:]):
            #    0        1      2        3       4       5            6
            # Revision, Part, Chapter, Section, Type, Sentence_num, Sentence
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            if not len(toks) == REQUIREMENTS_HEADER_TOKEN_COUNT:
                raise ValueError("%s %d Line %s tok len %d"
                              % (reqt, line_num+1, line, len(toks)))
            del toks[5]
            self.drop_lines.append(toks)

    def _read_checklists(self):
        for checklist_path in self.checklists:
            checklist_file = open(checklist_path)
            lines = [line.strip() for line in checklist_file.readlines()]
            checklist_file.close()

            if not lines[1] == CHECKLIST_HEADER:
                raise ValueError("Bad format: File %s first line is not %s"
                             % (checklist_path, CHECKLIST_HEADER))
            for x, line in enumerate(lines[2:]):
                line_num = x + 1
                tokens = [re.sub("'", "", tok.strip()) for tok in line.split("', ")]
                if not len(tokens) == 11:
                    raise ValueError("Bad format: File %s line %d: %s"
                                 % (checklist_path, line_num, tokens))
                if (not len(self.outline_lines)
                     or tokens[TOK_IDX_CHK_H_PART] == "Part 4"):
                    continue
                # Try to translate checklist references to complete references
                if tokens[TOK_IDX_CHK_H_SECTION].startswith("Sec. "):
                    tokens[TOK_IDX_CHK_H_SECTION] = tokens[TOK_IDX_CHK_H_SECTION][len("Sec. "):].strip()
                    if len(tokens[TOK_IDX_CHK_H_SECTION]) == 1:
                        tokens[TOK_IDX_CHK_H_SECTION] += ".1"

                reference = [tokens[TOK_IDX_CHK_H_REVISION], tokens[TOK_IDX_CHK_H_PART], tokens[TOK_IDX_CHK_H_CHAPTER], tokens[TOK_IDX_CHK_H_SECTION]]
                part_title = self.outline_reference[tokens[TOK_IDX_CHK_H_REVISION]][tokens[TOK_IDX_CHK_H_PART]][0]
                ch_title = self.outline_reference[tokens[TOK_IDX_CHK_H_REVISION]][tokens[TOK_IDX_CHK_H_PART]][1][tokens[TOK_IDX_CHK_H_CHAPTER]][0]
                sec_title = self.outline_reference[tokens[TOK_IDX_CHK_H_REVISION]][tokens[TOK_IDX_CHK_H_PART]][1][tokens[TOK_IDX_CHK_H_CHAPTER]][1][tokens[TOK_IDX_CHK_H_SECTION]]

                # Append translations of the references.
                for t_key in self.trans_keys:
                    t_rev, t_part, t_chap, t_sec = self._translator.translate(
                         tokens[TOK_IDX_CHK_H_REVISION], part_title, ch_title, sec_title, t_key)
                    tokens.extend([t_rev, t_part, t_chap, t_sec])
                tokens[TOK_IDX_CHK_H_PART] = part_title
                tokens[TOK_IDX_CHK_H_CHAPTER] = ch_title
                tokens[TOK_IDX_CHK_H_SECTION] = sec_title
                self.merge.append(tokens)
        self.sorted_merge = sorted(self.merge,
                                    key=operator.itemgetter(TOK_IDX_CHK_H_PART,
                                                    TOK_IDX_CHK_H_CHAPTER,
                                                    TOK_IDX_CHK_H_SECTION,
                                                    TOK_IDX_CHK_H_TYPE,
                                                    TOK_IDX_CHK_H_SENTENCE_NUM))


    def print_checklist(self):
        if self.sorted_merge == []:
            print "Nothing in sorted checklist."

        print self.header
        for item in self.sorted_merge:
            print "'" + "', '".join(item) + "'"

def create_parser():
    parser = OptionParser(description="Merge parsed checklist text files into a single checklist sorted by part, chapter, section, and revision")
    parser.add_option('-c', '--checklist',
            dest = 'checklist_filenames',
            action = 'append', type = 'string', default = [],
            help = 'Checklist file(s) created by parse_checklist.py',
            metavar = 'FILE')
    parser.add_option('-o', '--outlines',
            dest = 'outline_filenames',
            action = 'append', type = 'string', default = [],
            help = 'Outline file(s) created by parse_rapidio_standard.py',
            metavar = 'FILE')
    parser.add_option('-t', '--translation',
            dest = 'translation_filenames',
            action = 'append', type = 'string', default = [],
            help = 'Translation file(s) created by create_translation.py',
            metavar = 'FILE')
    parser.add_option('-r', '--requirements',
            dest = 'reqt_filepaths',
            action = 'append', type = 'string', default = [],
            help = 'Requirements file created by parse_rapidio_standard.py',
            metavar = 'FILE')
    parser.add_option('-m', '--manual_reqts',
            dest = 'manual_reqts',
            action = 'append', type = 'string', default = [],
            help = 'Manually maintained requirements files.',
            metavar = 'FILE')
    parser.add_option('-d', '--drop_reqts',
            dest = 'drop_reqts',
            action = 'append', type = 'string', default = [],
            help = 'Manually maintained drop requirements files.',
            metavar = 'FILE')

    return parser

def validate_options(options):
    if not len(options.checklist_filenames) and not len(options.reqt_filepaths):
        raise ValueError("Must enter at least one checklist/requirements filename.")

    for checklist in options.checklist_filenames:
        if not os.path.isfile(checklist):
            raise ValueError("Checklist file '%s' does not exist." % checklist)

    for outline in options.outline_filenames:
        if not os.path.isfile(outline):
            raise ValueError("Outline file '%s' does not exist." % outline)

    for translation in options.translation_filenames:
        if not os.path.isfile(translation):
            raise ValueError("Translation file '%s' does not exist." % translation)

    for reqt in options.reqt_filepaths:
        if not os.path.isfile(reqt):
            raise ValueError("Requirements file '%s' does not exist." % reqt)

    for man_reqt in options.manual_reqts:
        if not os.path.isfile(man_reqt):
            raise ValueError("Manually maintained requirements file '%s' does not exist." % man_reqt)

    for drop_reqt in options.drop_reqts:
        if not os.path.isfile(drop_reqt):
            raise ValueError("Manually maintained requirements file '%s' does not exist." % drop_reqt)

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

    merger = ChecklistMerger(options.checklist_filenames,
                             options.outline_filenames,
                             options.translation_filenames,
                             options.reqt_filepaths,
                             options.manual_reqts,
                             options.drop_reqts)
    merger.print_checklist()

if __name__ == '__main__':
    sys.exit(main())
