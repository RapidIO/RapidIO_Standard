#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Create a unified translation file for the RapidIO standards.

    Reads in translate_X.XtoY.Y.txt files created by check_all_outlines,
    and creates a base supporting all translations, and interfaces to
    translate forward or backwards from one revision to another.

"""

from optparse import OptionParser
from collections import OrderedDict
import re
import sys
import os
import logging

class RapidIOTranslationMerger(object):
    def _add_trans(self, rev_key, part, chapter, section, translation):
        if rev_key not in self.trans:
           self.trans.update({rev_key:{}})
        if part not in self.trans[rev_key]:
            self.trans[rev_key].update({part:{}})
        if chapter not in self.trans[rev_key][part]:
            self.trans[rev_key][part].update({chapter:{}})
        if section not in self.trans[rev_key][part][chapter]:
            self.trans[rev_key][part][chapter].update({section:[]})
        self.trans[rev_key][part][chapter][section].append(translation)

    def _add_no_fwd_trans(self, rev_key, part, chapter, section):
        if rev_key not in self.dead_ends:
           self.dead_ends.update({rev_key:{}})
        if part not in self.dead_ends[rev_key]:
            self.dead_ends[rev_key].update({part:{}})
        if chapter not in self.dead_ends[rev_key][part]:
            self.dead_ends[rev_key][part].update({chapter:[section]})
            return
        if section in self.dead_ends[rev_key][part][chapter]:
            raise ValueError("%s Duplicate Section '%s' found in '%s'"
                      % (self.trans_file, section, self.dead_ends[rev_key][part][chapter]))
        else:
            self.dead_ends[rev_key][part][chapter].append(section)

    def _init_translations(self):
        self.trans = {}
        self.trans_revs = []
        self.dead_ends = {}
        for trans in sorted(self.translations):
            self.trans_file = trans
            trans_file = open(trans)
            trans_lines = trans_file.readlines()
            trans_file.close()

            skip_until_old_items = False
            process_old_items = False
            for line_no, line in enumerate(trans_lines):
                line = line.strip()
                if line == "Unmatched new items, interleaved with old":
                   skip_until_old_items = True

                if line == "Unmatched old items":
                   skip_until_old_items = False
                   process_old_items = True
                   continue

                if skip_until_old_items:
                    continue

                toks = [tok.strip() for tok in line[1:-1].split("', '")]
                if process_old_items:
                    if not len(toks) == 4:
                        raise ValueError("%s:%d Old Items Toks != 4: %s"
                                       % (trans, line_no, toks))
                    logging.debug("Dead End: %s %s %s %s"
                                % (toks[0], toks[1], toks[2], toks[3]))
                    self._add_no_fwd_trans(toks[0], toks[1], toks[2], toks[3])
                    continue

                if not len(toks) == 8:
                    raise ValueError("%s:%d Toks != 8: %s"
                                   % (trans, line_no, toks))
                self._add_trans(toks[0], toks[1], toks[2], toks[3], toks[4:7])
                self._add_trans(toks[4], toks[5], toks[6], toks[7], toks[0:3])

    def __init__(self, translations):
        self.translations = translations
        self.first_rev = None

        self._init_translations()

    def print_translations(self):
        if self.trans == {}:
            print "Nothing in merged outline."

        print "Revision, Part, Chapter, Section, Translations"
        for rev_key in sorted(self.trans.keys()):
            for part_key in sorted(self.trans[rev_key].keys()):
                for chap_key in sorted(self.trans[rev_key][part_key].keys()):
                    for sec_key in sorted(self.trans[rev_key][part_key][chap_key].keys()):
                        for trans in self.trans[rev_key][part_key][chap_key][sec_key]:
                            key_list = [rev_key, part_key, chap_key, sec_key]
                            key_list.extend(trans)
                            print ", ".join(key_list)

def create_parser():
    parser = OptionParser()
    parser.add_option('-t', '--translate',
            dest = 'translation_filenames',
            action = 'append', type = 'string', default = [],
            help = 'Translation files map one standards to new names in another specification',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if not len(options.translation_filenames):
        print "Must enter at least one translation filename."
        sys.exit()

    for trans in options.translation_filenames:
        if not os.path.isfile(trans):
            print "File '" + trans +"' does not exist."
            sys.exit()

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

    validate_options(options)

    merger = RapidIOTranslationMerger(options.translation_filenames)
    merger.print_translations()

if __name__ == '__main__':
    sys.exit(main())
