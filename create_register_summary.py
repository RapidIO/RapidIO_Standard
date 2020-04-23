#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Create a summary of the RapidIO registers in CSV format.

    The summary merges the definitions from different parts of the RapidIO
    standard into a single, concise presentation.

"""

from optparse import OptionParser
from collections import OrderedDict
import re
import sys
import os
import logging
from constants import *
from create_translation import *

class RegisterFields(object):
    revision = None
    part = None
    chapter = None
    section = None
    block_id = None
    field_begin = -1
    field_end = 32
    field_name = "Unknown"
    field_desc = "No Description"

class RegisterSummaryLine(object):
    block_id = None
    field_begin = 0
    field_end = 31
    field_name = "Reserved"
    field_desc = ""
    revision = None
    part = None
    chapter = None
    section = None

class RegFields(object):
    def __init__(self, title, rev, part, chapter, secn):
        self.title = title
        self.rev = rev
        self.part = part
        self.chap = chapter
        self.secn = secn
        self.fields = OrderedDict()

class RegisterSummaryGenerator(object):
    def __init__(self, register_files, translation_files):
        self.translator = RapidIOTranslationMerger(translation_files)
        self.trans_keys = self.translator.trans.keys()
        self.trans_keys.sort()
        self.target_rev = None
        if len(self.trans_keys):
            self.target_rev = self.trans_keys[-1]

        self.register_files = register_files
        self.regs = []
        self.reg_blocks = {}
        self.registers = []
        for file_path in self.register_files:
            self.read_register_file(file_path)

    def parse_bit_field(self, bit_field_desc):
        toks = [t.strip() for t in bit_field_desc.split()]
        for idx, tok in enumerate(toks):
            if tok[-1] == '-':
                toks[idx] = tok + toks[idx + 1]
                del toks[idx + 1:idx + 2]

        begin_bit = -1;
        end_bit = -1;
        for tok in toks:
            if "0123456789".find(tok[0]) == -1:
                continue
            field_bits = [t.strip() for t in tok.split("-")]
            begin_bit = int(field_bits[0])
            try:
                if len (field_bits) > 1:
                    end_bit = int(field_bits[1])
                else:
                    end_bit = begin_bit
            except ValueError:
                return -1, -1;
        return begin_bit, end_bit

    def read_register_file(self, file_path):
        with open(file_path) as reg_file:
            reg_lines = [line.strip() for line in reg_file.readlines()]

        file_rev = ""
        for rev in self.trans_keys:
            if file_path.find(rev) >= 0:
                file_rev = rev
                break

        if not (reg_lines[0] == REGISTERS_HEADER):
            raise ValueError('Register file %s does not begin with "%s"' %
                             (file_path, REGISTERS_HEADER))

        for idx, line in enumerate(reg_lines[1:]):
            do_not_add = ["Reserved",
                          "Reserved (defined elsewhere)"]
            found = False
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            for item in do_not_add:
                if item in toks:
                    found = True
                    break;
            if found:
                continue
            reg = RegisterFields()
            reg.revision = toks[TOK_IDX_REG_REV]
            reg.part = toks[TOK_IDX_REG_PART]
            reg.chapter = toks[TOK_IDX_REG_CHAPTER]
            reg.section = toks[TOK_IDX_REG_SEC]
            reg.block_id = toks[TOK_IDX_REG_BLK]
            reg.field_begin, reg.field_end = self.parse_bit_field(toks[TOK_IDX_REG_BITS])
            if reg.field_begin == -1 or reg.field_end == -1:
                raise ValueError("Registers file %s line %d bad bit field: %s" %
                       (file_path, idx, toks[TOK_IDX_REG_BITS]))
            reg.field_name = toks[TOK_IDX_REG_FIELD]
            reg.field_desc = toks[TOK_IDX_REG_DESC]

            if not file_rev == self.target_rev and self.target_rev is not None:
                reg.revision, reg.part, reg.chapter, reg.section = self.translator.translate(toks[TOK_IDX_REG_REV],
                                              toks[TOK_IDX_REG_PART],
                                              toks[TOK_IDX_REG_CHAPTER],
                                              toks[TOK_IDX_REG_SEC],
                                              self.target_rev)
            self.regs.append(reg)

    def get_offset_substring(self, reg):
        offset = reg.section.find("Offset")
        if (offset < 0):
            return ""

        # Extract the offset portion of the section header.
        # Strip off the character after "Offset" (which could be 's' or
        # a space) and the last character, which should be a ')'
        offset_str = reg.section[offset + len("Offset") + 1:-1].strip()
        o_toks = [tok.strip() for tok in offset_str.split(" ")]
        if o_toks[0][-1] == ",":
            if reg.block_id == "STD_REG":
                offset_str = "LIST FOR STD REG"
        else:
            # The first offset token is not part of a comma separated
            # list, so it must be a single offset.  Truncate any additional
            # characters.
            offset_str = o_toks[0]
        # Single hexadecimal digit offset, which breaks string based
        # sorting.  Fix it by prepending a 0.
        if len(offset_str) == 3:
            offset_str = "0x0" + offset_str[-1]
        return offset_str
            
    def summarize_registers(self):
        for reg in self.regs:
            if not reg.block_id in self.reg_blocks:
                self.reg_blocks[reg.block_id] = OrderedDict()
            offset_str = self.get_offset_substring(reg)
            if offset_str == "":
                raise ValueError("No offset found in %s" % reg.section)
            if offset_str == "LIST FOR STD REG":
                continue
            title_toks = [t.strip() for t in reg.section.split()]
            title = ""
            for tok in title_toks[1:]:
                if tok[0] == "(":
                    break;
                title = title + " " + tok
            title = title.strip()
            if not offset_str in self.reg_blocks[reg.block_id]:
                self.reg_blocks[reg.block_id][offset_str] = RegFields(
                                     title, reg.revision, reg.part, reg.chapter,
                                     reg.section)
            #if reg.field_begin in self.reg_blocks[reg.block_id][offset_str].fields:
            #    temp = self.reg_blocks[reg.block_id][offset_str].fields[reg.field_begin]
            #    raise ValueError("Duplicate field definition? '%s' XXX '%s'" %
            #                     ("', '".join([reg.part, reg.section,
            #                                  reg.block_id, offset_str,
            #                                  str(reg.field_begin)]),
            #                      "', '".join([temp.part, temp.section, temp.block_id, temp.field_name])))
            self.reg_blocks[reg.block_id][offset_str].fields[reg.field_begin] = reg

    #INFW: Currently only supports a single revision and a single definition
    #      for each bit.
    def print_registers(self):
        reserved = RegisterSummaryLine()

        for block in sorted(self.reg_blocks.keys()):
            for offset in sorted(self.reg_blocks[block].keys()):
                print("'%s'" % "', '".join([block, offset,
                                   self.reg_blocks[block][offset].title]))
                for bitstart in sorted(self.reg_blocks[block][offset].fields.keys()):
                    reg = self.reg_blocks[block][offset].fields[bitstart]
                    bit_str = str(reg.field_begin)
                    if not reg.field_begin == reg.field_end:
                        bit_str = bit_str + ":" + str(reg.field_end)
                    print("'%s'" % "', '".join([bit_str, reg.field_name,
                                               # reg.field_desc,
                                               reg.part,
                                               # reg.chapter,
                                               reg.section]))

def create_parser():
    parser = OptionParser()
    parser.add_option('-r', '--reg_file',
            dest = 'register_files',
            action = 'append', type = 'string', default = [],
            help = 'Register file created by parse_rapidio_standard.py or manually',
            metavar = 'FILE')
    parser.add_option('-t', '--trans_file',
            dest = 'translation_files',
            action = 'append', type = 'string', default = [],
            help = 'Translation files between revisions',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if options.register_files == []:
        print ("Must enter at least one register file name.")
        sys.exit()

    for file_path in options.register_files:
        if not os.path.isfile(file_path):
            print ("File '%s' does not exist." % file_path)
            sys.exit()

    for file_path in options.translation_files:
        if not os.path.isfile(file_path):
            print ("File '%s' does not exist." % file_path)
            sys.exit()

    return options

def main(argv = None):
    logging.basicConfig(level=logging.WARNING)
    parser = create_parser()
    if argv is None:
        argv = sys.argv[1:]

    (options, argv) = parser.parse_args(argv)
    if len(argv) != 0:
        print ('Invalid argument!')
        print
        parser.print_help()
        return -1

    options = validate_options(options)

    summary = RegisterSummaryGenerator(options.register_files,
                                       options.translation_files)
    summary.summarize_registers()
    summary.print_registers()

if __name__ == '__main__':
    sys.exit(main())
