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
READ_ONLY = 'R'

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

    while not ((check_passed == ACCEPT)
            or (check_passed == QUIT)
            or (check_passed == READ_ONLY)):
        excel.edit_excel();
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
    new_section_revisions = ["2.2", "3.2", "4.0", "4.1"]
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

def strip_apostrophes(toks):
    for i, tok in enumerate(toks):
        if len(tok) <= 0:
            continue
        if tok[0] == "'":
            toks[i] = toks[i][1:]
        if tok[-1] == "'":
            toks[i] = toks[i][:-1]

def check_manual_translation_line(line, chk_parms):
    toks = [tok.strip() for tok in line[1:-1].split("', '")]
    strip_apostrophes(toks)
    new_line = "'%s'\n" % "', '".join(toks[0:4])
    old_line = "'%s'\n" % "', '".join(toks[4:])
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
    manual_translations = ["1.3to2.2", "2.2to3.2", "4.0to4.1"]
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

def check_manual_requirement_line(line, chk_parms):
    toks = [tok.strip() for tok in line.split("', '")]
    strip_apostrophes(toks)

    ref_line = "'%s'\n" % "', '".join(toks[0:4])
    return ref_line in chk_parms["outline"]

def check_manual_requirements(excel, chk_parms):
    rc = ACCEPT
    missing = False

    if excel.lines[0] not in chk_parms["original"]:
        print("Row 1 not found in %s." % (excel.text_filepath))
        print("Row: %s" % excel.lines[0])
        missing = True

    for i, line in enumerate(excel.lines[1:]):
        if check_manual_requirement_line(line, chk_parms):
            continue
        print("Row %i reference not found in outline" % (i + 2))
        print("Row: %s" % line)
        missing = True

    if missing:
        rc = get_quit_accept_edit()
    return rc

def edit_manual_requirements():
    manual_requirements = ["3.2", "4.0", "4.1"]
    print("Choose the manual requirements:")
    for i, rev in enumerate(manual_requirements):
        print("%d : %s" % (i, rev))
    inp = raw_input("Select option, or 'X' to exit:")
    try:
        idx = int(inp)
    except ValueError:
        return
    if not (idx in range(0, len(manual_requirements))):
        return
    rev = manual_requirements[idx]

    chk_lines = {}
    filepath = os.path.join("Standards", "manual_reqts_%s.txt" % rev)
    with open(filepath) as f:
        chk_lines["original"] = f.readlines()
    outline_path = os.path.join("Standards", "outline_%s.txt" % rev)
    with open(outline_path) as f:
        chk_lines["outline"] = f.readlines()
    edit_file(filepath, check_manual_requirements, chk_lines)

def edit_drop_requirements():
    manual_requirements = ["3.2"]
    print("Choose the manual drop requirements:")
    for i, rev in enumerate(manual_requirements):
        print("%d : %s" % (i, rev))
    inp = raw_input("Select option, or 'X' to exit:")
    try:
        idx = int(inp)
    except ValueError:
        return
    if not (idx in range(0, len(manual_requirements))):
        return
    rev = manual_requirements[idx]

    chk_lines = {}
    filepath = os.path.join("Standards", "manual_drop_%s.txt" % rev)
    with open(filepath) as f:
        chk_lines["original"] = f.readlines()
    outline_path = os.path.join("Standards", "outline_%s.txt" % rev)
    with open(outline_path) as f:
        chk_lines["outline"] = f.readlines()
    edit_file(filepath, check_manual_requirements, chk_lines)

def check_optional_checklist_item_line(line, chk_parms):
    toks = [tok.strip() for tok in line.split("', '")]
    strip_apostrophes(toks)

    name = toks[TOK_IDX_OPT_CHK_H_TABLE_NAME]
    item = toks[TOK_IDX_OPT_CHK_H_CHECKLIST_ID]
    if name not in chk_parms["items"]:
        return False
    return item in chk_parms["items"][name]

def check_optional_checklist_items(excel, chk_parms):
    rc = ACCEPT
    missing = False

    for idx in range(0,1):
        if excel.lines[0] not in chk_parms["original"]:
            print("Row %d not found in %s." % (idx, excel.text_filepath))
            print("Row: %s" % excel.lines[idx])
            missing = True

    for i, line in enumerate(excel.lines[1:]):
        if check_optional_checklist_item_line(line, chk_parms):
            continue
        print("Row %i table or item not found in checklist" % (i + 2))
        print("Row: %s" % line)
        missing = True

    if missing:
        rc = get_quit_accept_edit()
    return rc

def edit_optional_checklist_items():
    optional_items = {"1.3":["rev1_3_rio_chklist_optional.txt",
                             "rev1_3_rio_chklist.txt"],
                      "2.2":["rapidio_interop_checklist_rev2_2_optional.txt",
                             "rapidio_interop_checklist_rev2_2.txt"],
                      "Err":["ErrorManagementChecklist_optional.txt",
                             "ErrorManagementChecklist.txt"]
                     }
    revs = sorted(optional_items.keys())
    print("Choose the checklist optional items file:")
    for i, rev in enumerate(revs):
        print("%d : %s, file %s" % (i, rev, optional_items[rev][0]))
    inp = raw_input("Select option, or 'X' to exit:")
    try:
        idx = int(inp)
    except ValueError:
        return
    if not (idx in range(0, len(optional_items))):
        return
    rev = revs[idx]
    chk_lines = {}
    filepath = os.path.join("Historic_Checklists", optional_items[rev][0])
    with open(filepath) as f:
        chk_lines["original"] = f.readlines()
    items_path = os.path.join("Historic_Checklists", optional_items[rev][1])
    with open(items_path) as f:
        checklist = f.readlines()
    chk_lines["items"] = {}
    name_idx = TOK_IDX_CHK_H_TABLE_NAME
    item_idx = TOK_IDX_CHK_H_CHECKLIST_ID
    for line in checklist[2:]:
        toks = [tok.strip() for tok in line[1:-1].split("', '")]
        name = toks[name_idx]
        item = toks[item_idx]
        if name not in chk_lines["items"]:
            chk_lines["items"][name] = []
        if item not in chk_lines["items"][name]:
            chk_lines["items"][name].append(item)

    edit_file(filepath, check_optional_checklist_items, chk_lines)

def check_testcase_line(line, chk_parms):
    rc = False
    toks = [tok.strip() for tok in line.split("', '")]
    strip_apostrophes(toks)

    if len(toks) != TOK_IDX_TC_H_TOK_COUNT:
        print("Column count %d, not %d" % (len(toks), TOK_IDX_TC_H_TOK_COUNT))
        return False

    uids = toks[TOK_IDX_TC_H_CONST_REFS]
    uids = uids.replace("\\n", " ")
    uid_toks = [tok.strip() for tok in uids.split(" ")]
    missing = []
    for uid in uid_toks:
        if uid == '':
            continue
        if uid not in chk_parms["uids"]:
            missing.append(uid)
    if missing != []:
        print("Missing references: '%s'" % "', '".join(missing))
    return missing == []

def check_testcases(excel, chk_parms):
    rc = ACCEPT
    missing = False

    for idx in range(0,1):
        if excel.lines[0] not in chk_parms["original"]:
            print("Row %d not found in %s." % (idx, excel.text_filepath))
            print("Row: %s" % excel.lines[idx])
            missing = True

    for i, line in enumerate(excel.lines[1:]):
        if check_testcase_line(line, chk_parms):
            continue
        print("Row %i has error." % (i + 2))
        print("Row: %s" % line)
        missing = True

    if missing:
        rc = get_quit_accept_edit()
    return rc

def edit_testcases():
    testcases = {"Part  1":["NREAD/NWRITE/NWRITE_R/SWRITE/MAINTENANCE",
                           "part_1_test_plan.txt"],
                 "Part  2":["Messaging and Doorbells",
                           "part_2_test_plan.txt"],
                 "Part  6 Ch 5":["IDLE3 State Machines",
                           "part_6_ch5_test_plan.txt"],
                 "Part 10":["Data Streaming",
                           "part_10_test_plan.txt"]}
    print("Choose the testcase file:")
    keys = sorted(testcases.keys())
    for i, key in enumerate(keys):
        print("%d : %s, %s" % (i, key, testcases[key][0]))
    inp = raw_input("Select option, or 'X' to exit:")
    try:
        idx = int(inp)
    except ValueError:
        return
    if not (idx in range(0, len(keys))):
        return
    chk_lines = {}
    filepath = os.path.join("Testcases", testcases[keys[idx]][1])
    with open(filepath) as f:
        chk_lines["original"] = f.readlines()
    chkpath = os.path.join("Historic_Checklists", "merged_sorted_db.txt")
    chk_lines["uids"] = []
    with open(chkpath) as f:
        for line in f.readlines():
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            chk_lines["uids"].append(toks[TOK_IDX_DB_H_CONST_REF])
    edit_file(filepath, check_testcases, chk_lines)

def review_requirements_check(unused, unused2):
    return READ_ONLY

def review_requirements():
    text_file_path = os.path.join("Historic_Checklists", "merged_sorted_db.txt")
    edit_file(text_file_path, review_requirements_check, {})

def recover_spreadsheet():
    inp = raw_input("Enter name of spreadsheet, or X to exit:")
    if inp == "X":
        return
    elif not os.path.isfile(inp):
        print("File '%s' not found. Exiting..." % inp)
        return
    spreadsheet_path = inp

    inp = raw_input("Enter name of text file, or X to exit:")
    if inp == "X":
        return
    text_file_path = inp
    updated = ExcelEditor(text_file_path, spreadsheet_path, "XL")
    updated.write_text()

def file_to_spreadsheet():
    inp = raw_input("Enter name of text file, or X to exit:")
    if inp == "X":
        return
    if not os.path.isfile(inp):
        print("File '%s' not found. Exiting..." % inp)
        return
    text_file_path = inp

    inp = raw_input("Enter name of spreadsheet, or X to exit:")
    if inp == "X":
        return
    spreadsheet_path = inp

    updated = ExcelEditor(text_file_path, spreadsheet_path)
    updated.write_excel()

new_sections = '1'
manual_translations = '2'
manual_requirements = '3'
drop_requirements = '4'
optional_items = '5'
testcases = '6'
requirements_db = '7'
recovery = '8'
edit_any = '9'
exit_option = 'X'
cmd_options = { new_sections:'New sections',
                manual_translations:'Manual translations',
                manual_requirements:'Manual requirements',
                drop_requirements:'Drop requirements',
                optional_items:'Optional checklist items',
                testcases:'Testcase definitions',
                requirements_db:'Requirements Database (read only)',
                recovery:'Recover a spreadsheet, convert to file. No checking',
                edit_any:'Convert a file to a spreadsheet.',
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
        elif temp == drop_requirements:
            edit_drop_requirements()
        elif temp == optional_items:
            edit_optional_checklist_items()
        elif temp == testcases:
            edit_testcases()
        elif temp == requirements_db:
            review_requirements()
        elif temp == recovery:
            recover_spreadsheet()
        elif temp == edit_any:
            file_to_spreadsheet()
        elif temp == exit_option:
            break
        else:
            print("'%s' unknown option." % temp)
    sys.exit(0)

if __name__ == '__main__':
    sys.exit(main())
