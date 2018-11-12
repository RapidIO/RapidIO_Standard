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

def edit_manual_translations():
    print("Not implemented...")
    return

def edit_manual_requirements():
    print("Not implemented...")
    return

def main(argv = None):
    global new_sections
    global manual_translations
    global exit_option
    logging.basicConfig(level=logging.WARN)
    temp = ''

    # try:
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
    # except Exception as e:
    #     print("Exception!!")
    #     print(e)
    sys.exit(0)

if __name__ == '__main__':
    sys.exit(main())
