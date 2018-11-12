#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Safely edits files and checks that they are consistent with others.

    Command line interactive program which allows users to edit files
    using XLSX.
"""

from optparse import OptionParser
from collections import OrderedDict
import operator
import re
import sys
import os
import logging
import copy

from difflib import Differ
from constants import *
from create_translation import *
from openpyxl import Workbook
from openpyxl.styles import Alignment
from openpyxl import load_workbook
import codecs
import subprocess

from make_spreadsheet import *

QUIT = 'Q'
ACCEPT = 'A'
EDIT = 'E'

options = [QUIT, ACCEPT, EDIT]

def get_quit_accept_edit():
    inp = ''
    prompt=("Enter '%s' Quit (no save), '%s' Accept (save), '%s' Edit: "
            % (QUIT, ACCEPT, EDIT))
    while inp not in options:
        inp = raw_input(prompt)
    return inp

def edit_file(filepath, check, check_parms):
    filepath_xls = filepath + ".xlsx"
    excel = ExcelEditor(filepath, filepath_xls)
    excel.write_excel()
    check_passed = ''

    while not ((check_passed == ACCEPT) or (check_passed == QUIT)):
        cmd = "xdg-open %s" % filepath_xls
        process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
        output, error = process.communicate()
        updated = ExcelEditor(filepath, filepath_xls, "XL")
        check_passed = check(updated, check_parms)

    if check_passed == ACCEPT:
        updated.write_text()

def check_new_sections(excel, chk_parms):
    rc = ACCEPT
    missing = False
    for i, line in enumerate(excel.lines):
        if line in chk_parms:
            continue
        print("Row %i not found in outline." % (i + 1))
        print("Row: %s" % line)
        missing = True

    if missing:
        rc = get_quit_accept_edit()
    return rc

def edit_new_sections():
    new_section_revisions = ["2.2", "3.2", "4.0"]
    print("Choose the revision for new sections:")
    for i, rev in enumerate(new_section_revisions):
        print("%d : Revision %s" % (i, rev))
    print("Enter anything else to cancel.")
    inp = raw_input('Select option, or -1 to exit:')
    try:
        idx = int(inp)
    except ValueError:
        return
    if idx >= len(new_section_revisions):
        return
    rev = new_section_revisions[idx]
    filepath = os.path.join("Standards", "new_sections_%s.txt" % rev)
    outline_path = os.path.join("Standards", "outline_%s.txt" % rev)
    with open(outline_path) as f:
        chk_lines = f.readlines()
    edit_file(filepath, check_new_sections, chk_lines)

def check_manual_translation_line(line, chk_parms):
    toks = [tok.strip() for tok in line[1:-1].split("', '")]
    for i, tok in enumerate(toks):
        if tok[0] == "'":
            toks[i] = toks[i][1:]
        if tok[-1] == "'":
            toks[i] = toks[i][:-1]
    new_line = "'%s'\n" % "', '".join(toks[0:4])
    old_line = "'%s'\n" % "', '".join(toks[4:])
    #print("TOKS:%s" % toks)
    #print("NEW :%s" % new_line)
    #print("OLD :%s" % old_line)
    if (old_line in chk_parms["OLD"]) and (new_line in chk_parms["NEW"]):
        return True
    return False

def check_manual_translations(excel, chk_parms):
    rc = ACCEPT
    missing = False

    if excel.lines[0] not in chk_parms["original"]:
        print("Row 1 not found in %s." % (excel.text_filepath))
        print("Row: %s" % excel.lines[0])
        missing = True

    for i, line in enumerate(excel.lines[1:]):
        if check_manual_translation_line(line, chk_parms):
            continue
        print("Row %i not found in outlines." % (i + 2))
        print("Row: %s" % line)
        missing = True

    if missing:
        rc = get_quit_accept_edit()
    return rc

def edit_manual_translations():
    manual_translations = ["1.3to2.2", "2.2to3.2"]
    print("Choose the manual translation:")
    for i, rev in enumerate(manual_translations):
        print("%d : %s" % (i, rev))
    print("Enter anything else to cancel.")
    inp = raw_input("Select option, or 'X' to exit:")
    try:
        idx = int(inp)
    except ValueError:
        return
    if not (idx in range(0, len(manual_translations))):
        return
    rev = manual_translations[idx]
    revs = [tok.strip() for tok in rev.split("to")]

    chk_lines = {}
    filepath = os.path.join("Standards", "manual_%s.txt" % rev)
    with open(filepath) as f:
        chk_lines["original"] = f.readlines()
    old_path = os.path.join("Standards", "outline_%s.txt" % revs[0])
    with open(old_path) as f:
        chk_lines["OLD"] = f.readlines()
    new_path = os.path.join("Standards", "outline_%s.txt" % revs[1])
    with open(new_path) as f:
        chk_lines["NEW"] = f.readlines()
    edit_file(filepath, check_manual_translations, chk_lines)

def edit_manual_requirements():
    print("Not implemented...")
    return

new_sections = '1'
manual_translations = '2'
manual_requirements = '3'
exit_option = 'X'
cmd_options = { new_sections:'New sections',
                manual_translations:'Manual translations',
                manual_requirements:'Manual requirements',
                exit_option:'Exit' }

def print_cmd_options():
    for key in sorted(cmd_options.keys()):
        print("%s: %s" % (key, cmd_options[key]))

def main(argv = None):
    global new_sections
    global manual_translations
    global exit_option
    logging.basicConfig(level=logging.WARN)
    temp = ''

    while temp != exit_option:
        print_cmd_options()
        temp = raw_input('Select option:')
        if temp == new_sections:
            edit_new_sections()
        elif temp == manual_translations:
            edit_manual_translations()
        elif temp == manual_requirements:
            edit_manual_requirements()
        elif temp == exit_option:
            break
        else:
            print("'%s' unknown option." % temp)
    sys.exit(0)

if __name__ == '__main__':
    sys.exit(main())
