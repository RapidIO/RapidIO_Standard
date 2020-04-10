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
    def __init__(self, register_file):
        self.register_file = register_file
        self.regs = []
        self.reg_blocks = {}
        self.read_register_file()

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

    def read_register_file(self):
        self.registers = []
        with open(self.register_file) as reg_file:
            reg_lines = [line.strip() for line in reg_file.readlines()]

        if not (reg_lines[0] == REGISTERS_HEADER):
            raise ValueError('Register file does not begin with "%s"' % REGISTERS_HEADER)

        for idx, line in enumerate(reg_lines[1:]):
            do_not_add = ["Reserved", "Implementation Defined"]
            found = False
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            #if not len(toks) == TOK_IDX_REG_TOK_COUNT:
            #    raise ValueError("Registers file %s line %d bad format: %s" %
            #           (self.register_file, idx, line))
            for item in do_not_add:
                for tok in toks:
                    if not tok.find(item) == -1:
                        found = True
                        break;
                if found:
                    break
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
                       (self.register_file, idx, toks[TOK_IDX_REG_BITS]))
            reg.field_name = toks[TOK_IDX_REG_FIELD]
            reg.field_desc = toks[TOK_IDX_REG_DESC]
            self.regs.append(reg)
            
    def summarize_registers(self):
        for reg in self.regs:
            if not reg.block_id in self.reg_blocks:
                self.reg_blocks[reg.block_id] = OrderedDict()
            offset = reg.section.find("Offset")
            if (offset < 0):
                raise ValueError("Register %s No offset found" % reg.sect)
            offset_str = reg.section[offset + len("Offset"):-1].strip()
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
            if reg.field_begin in self.reg_blocks[reg.block_id][offset_str].fields:
                temp = self.reg_blocks[reg.block_id][offset_str].fields[reg.field_begin]
                raise ValueError("Duplicate field definition? '%s' XXX '%s'" %
                                 ("', '".join([reg.part, reg.section,
                                              reg.block_id, offset_str,
                                              str(reg.field_begin)]),
                                  "', '".join([temp.part, temp.section, temp.block_id, temp.field_name])))
            self.reg_blocks[reg.block_id][offset_str].fields[reg.field_begin] = reg

    #INFW: Currently only supports a single revision and a single definition
    #      for each bit.
    def print_registers(self):
        reserved = RegisterSummaryLine()

        for block in sorted(self.reg_blocks.keys()):
            for offset in self.reg_blocks[block].keys():
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
            dest = 'register_file',
            action = 'store', type = 'string',
            help = 'Register file created by parse_rapidio_standard.py',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if options.register_file is None:
        print ("Must enter register file name.")
        sys.exit()

    if not os.path.isfile(options.register_file):
        print ("File '" + options.register_file +"' does not exist.")
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

    summary = RegisterSummaryGenerator(options.register_file)
    summary.summarize_registers()
    summary.print_registers()

if __name__ == '__main__':
    sys.exit(main())
