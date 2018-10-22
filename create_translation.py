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
from constants import *

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
        header = [tok.strip() for tok in TRANSLATION_HEADER.split(",")]
        for trans in sorted(self.translations):
            self.trans_file = trans
            trans_file = open(trans)
            trans_lines = [line.strip() for line in trans_file.readlines()]
            trans_file.close()

            actual = [tok.strip() for tok in trans_lines[0][1:-1].split("', '")]
            if (actual != header):
                raise ValueError("Bad format: File %s first line is %s not %s"
                         % (self.trans_file, actual, header))

            skip_until_old_items = False
            process_old_items = False
            for line_no, line in enumerate(trans_lines[1:]):
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
                self._add_trans(toks[0], toks[1], toks[2], toks[3], toks[4:8])
                self._add_trans(toks[4], toks[5], toks[6], toks[7], toks[0:4])

    def __init__(self, translations):
        self.translations = translations
        self.first_rev = None

        self._init_translations()

    def print_translations(self):
        if self.trans == {}:
            print "Nothing in merged outline."

        header_items = [item.strip() for item in TRANSLATION_HEADER.split(",")]
        print ("'%s'" % ("', '".join(header_items)))
        for rev_key in sorted(self.trans.keys()):
            for part_key in sorted(self.trans[rev_key].keys()):
                for chap_key in sorted(self.trans[rev_key][part_key].keys()):
                    for sec_key in sorted(self.trans[rev_key][part_key][chap_key].keys()):
                        for trans in self.trans[rev_key][part_key][chap_key][sec_key]:
                            key_list = [rev_key, part_key, chap_key, sec_key]
                            key_list.extend(trans)
                            print ", ".join(key_list)

    BKWD = "backward"
    FWD = "forward"

    def _translate(self, rev_range, part, chapter, section, direction):
        logging.debug("_trans: %s %s %s %s %s"
                   % (rev_range, part, chapter, section, direction))
        if direction == self.FWD:
            try:
                if section in self.dead_ends[rev_range[0]][part][chapter]:
                    logging.debug("Dead Rev : %s" % rev_range[0])
                    return rev_range[0], part, chapter, section
            except:
                logging.debug("Alive Rev: %s" % rev_range[0])
                pass
        try:
            translations = self.trans[rev_range[0]][part][chapter][section]
            logging.debug("Translate: %d" % len(translations))
            for idx, trans in enumerate(translations):
                logging.debug("Trans    : %d %s" % (idx, trans))
                if trans[0] == rev_range[1]:
                    if len(rev_range) == 2:
                        logging.debug("Translate  Done: %s %s %s %s"
                                    % (trans[0], trans[1], trans[2], trans[3]))
                        return trans[0], trans[1], trans[2], trans[3]
                    logging.debug("TransNext: %s %s %s %s %s"
                    % (rev_range[1:], trans[1], trans[2], trans[3], direction))
                    return self._translate(rev_range[1:], trans[1], trans[2], trans[3], direction)
            raise ValueError("%s %s %s %s: No translation to revison %s"
                             % (rev_range[0], part, chapter, section))
        except:
            if len(rev_range) == 1:
                logging.debug("Translate  End: %s %s %s %s"
                                    % (rev_range[0], part, chapter, section))
                return rev_range[0], part, chapter, section
            logging.debug("TransDown: %s %s %s %s %s"
               % (rev_range[1:], part, chapter, section, direction))
            return self._translate(rev_range[1:], part, chapter, section, direction)

    def _translate_backward(self, revision, part, chapter, section, target_revision):
        revs = sorted(self.trans.keys())
        first_rev = revs.index(target_revision)
        last_rev = revs.index(revision)
        rev_range = revs[first_rev:last_rev + 1]
        rev_range.reverse()
        return self._translate(rev_range, part, chapter, section, self.BKWD)

    def _translate_forward(self, revision, part, chapter, section, target_revision):
        revs = sorted(self.trans.keys())
        first_rev = revs.index(revision)
        last_rev = revs.index(target_revision)
        rev_range = revs[first_rev:last_rev + 1]
        return self._translate(rev_range, part, chapter, section, self.FWD)

    def translate(self, revision, part, chapter, section, target_revision):
        if revision not in self.trans.keys():
            raise ValueError("Revision %s not in %s." % (revision, self.trans.keys()))
        if target_revision not in self.trans.keys():
            raise ValueError("Revision %s not in %s." % (target_revision, self.trans.keys()))

        if revision > target_revision:
            logging.debug("Translate: Backward")
            return self._translate_backward(revision, part, chapter, section, target_revision)
        elif revision < target_revision:
            logging.debug("Translate: Forward")
            return self._translate_forward(revision, part, chapter, section, target_revision)
        logging.debug("Translate: %s to %s" % (revision, target_revision))
        return revision, part, chapter, section

def create_parser():
    parser = OptionParser()
    parser.add_option('-t', '--translate',
            dest = 'translation_filenames',
            action = 'append', type = 'string', default = [],
            help = 'Translation files map one standards to new names in another specification',
            metavar = 'FILE')
    parser.add_option('-o', '--outline',
            dest = 'outline',
            action = 'store', type = 'string', default=None,
            help = 'Outline file to translate',
            metavar = 'FILE')
    parser.add_option('-v', '--version',
            dest = 'version',
            action = 'store', type = 'string', default=None,
            help = 'Version to translate specified outline to.',
            metavar = 'VERSION')
    return parser

def validate_options(options):
    if not len(options.translation_filenames):
        print ("Must enter at least one translation filename.")
        sys.exit()

    for trans in options.translation_filenames:
        if not os.path.isfile(trans):
            print ("File '%s' does not exist." % trans)
            sys.exit()

    if options.outline is not None:
        if not os.path.isfile(options.outline):
            print ("File '%s' does not exist." % options.outline)
            sys.exit()
        if options.version is None:
            print ("Must enter version when outline file is specified.")
            sys.exit()

def main(argv = None):
    logging.basicConfig(filemode='w', level=logging.WARN,
                        format='[%(levelname)s] %(message)s')
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
    if options.outline is None:
        merger.print_translations()
        return 0

    # Test Merger
    outline_file = open(options.outline)
    outline_lines = [line.strip() for line in outline_file.readlines()]
    outline_file.close()

    for idx, line in enumerate(outline_lines[1:]):
        tokens = [tok.strip() for tok in line[1:-1].split("', '")]
        if not len(tokens) == 4:
            print ("Line %d: %d tokens %s" % (idx, len(tokens), tokens))
            return 1
        logging.info("Input    : '%s' to '%s'"
                  % ("', '".join(tokens), options.version))
        trans_rev, trans_part, trans_chap, trans_sec = merger.translate(
                   tokens[0], tokens[1], tokens[2], tokens[3], options.version)
        trans_line = "'%s'" % "', '".join([trans_rev, trans_part, trans_chap, trans_sec])
        if not (trans_part == tokens[1] and trans_chap == tokens[2] and trans_sec == tokens[3]):
            line = "- " + line
            trans_line = "+ " + trans_line
        print (line)
        print (trans_line)

if __name__ == '__main__':
    sys.exit(main())
