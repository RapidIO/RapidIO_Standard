#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Parse the Data Streaming checklist XML file

    Parses checklist and prints one line of output for each checklist item.
    Each line has the following content:
    - Revision (enterend by user)
    - Part Number (1-13)
    - Chapter Number
    - Section Number
    - Type (Requirement)
    - Sentence
    - Checklist item reference
    Note that if there is more than one specification reference in the
    checklist, then one line of output is displayed for each specification
    reference.
"""

from optparse import OptionParser
import re
import sys
import os
import copy

PRINT_TRACE = False

REVISION = "Revision"
PART = "Part"
CHAPTER = "Chapter"
SECTION = "Section"
TYPE = "TYPE"
SENTENCE = "Sentence"
CHKLIST_ID = "Checklist_ID"

REQTS = {REVISION:None,
         PART:None,
         CHAPTER:None,
         SECTION:None,
         TYPE:None,
         SENTENCE:None,
         CHKLIST_ID:None}

TYPE_RECOMMENDATION = "Recommendation"
TYPE_REQUIREMENT = "REQUIREMENT"

def create_parser():
    parser = OptionParser()
    parser.add_option('-f', '--file',
            dest = 'filename_of_checklist',
            action = 'store', type = 'string',
            help = 'Compliance checklist in XML format.',
            metavar = 'FILE')
    parser.add_option('-r', '--revision',
            dest = 'revision_number',
            action = 'store', type = 'string', default="1.0",
            help = 'Revision identifier for the checklist file.',
            metavar = 'REVISION')
    parser.add_option('-p', '--part',
            dest = 'part_number',
            action = 'store', type = 'string', default="1",
            help = 'Part number for the checklist file.',
            metavar = 'PART')
    return parser

def validate_options(options):
    if options.filename_of_checklist is None:
        print "Must enter file name of checklist."
        sys.exit()

    if not os.path.isfile(options.filename_of_checklist):
        print "File '" + options.filename_of_checklist +"' does not exist."
        sys.exit()

    if options.part_number is None:
        options.part_number = '0'
    else:
        part_number = 0
        try:
            part_number = int(options.part_number)
        except ValueError:
             print "Part number must be an integer."
             sys.exit()
        if part_number < 1 or part_number > 12:
             print "Part number must be between 1 and 12, inclusive."
             sys.exit()

    print "options revision_number:", options.revision_number
    pattern = r"[1-4]\.[0-3]|[1-4]\.[1-3]\.[1-3]"
    regex = re.compile(pattern)
    match = regex.match(options.revision_number)
    if not match:
        print "Revision must be of the form X.Y or X.Y.Z,"
        print "where X, Y and Z are single digit numbers"
        print "X is 1-4."
        print "Y is 0-3."
        print "Z is 1-3."
        sys.exit()
    return options

def cleanup_text(text):
    text = re.sub('\n', ' ', text)
    text = re.sub('\t', '', text)
    text = re.sub('\r', ' ', text)

    text = re.sub(r'\<[^>]+\>', "", text)

    end_partial_xml = ">"
    start_txt = text.find(end_partial_xml)
    if start_txt >= 0:
        start_txt += len(end_partial_xml)
        text = text[start_txt:]
    return text.strip()

# Parses the first non-empty column, looking for one of two patterns:
# A) [0-9]*\. (digits 0-9, followed by a period)
#    In this case, the requirement sentence is found in the next column.
# B) ITEM [0-9]+[A-Z][0-9]*: SENTENCE"
#    In this case, the requirement sentence is part of the checklist item.
# The return is an updated requirement with the CHECKLIST_ID and SENTENCE
# updated based on the above.
#
# Additionally, the PART entry is updated with the column number which
# should have the specification reference

def get_checklist_item_and_sentence(cols, reqt, options):
    ITEM_CHKLIST = "ITEM "
    CHKLIST_RE = r"([0-9]+\.)"
    checklist_pattern = re.compile(CHKLIST_RE)
    column = ''
    item_col = -1

    for i, col in enumerate(cols):
        column = cleanup_text(col)
        item_col = i
        if not column == '':
            break

    if column == '':
        return reqt

    checklist_id = None

    if column[0:len(ITEM_CHKLIST)] == ITEM_CHKLIST:
        colon = column.find(":")
        if colon > 0:
            reqt[CHKLIST_ID] = column[len(ITEM_CHKLIST):colon].strip()
            reqt[SENTENCE] = column[colon + 1:].strip()
            reqt[TYPE] = "REQUIREMENT"
            reqt[PART] = item_col + 1
            return reqt

    result = checklist_pattern.match(column)
    if result:
        reqt[CHKLIST_ID] = result.group(0).strip()
        reqt[SENTENCE] = cleanup_text(cols[item_col + 1])
        reqt[TYPE] = "REQUIREMENT"
        reqt[PART] = item_col + 2

    return reqt

# Parse first column which has one or more lines of the form:
# Part X, Sec. Chapter.Y.Z...
# Returns one requirement for each line, with the fields
# Part, Chapter, and Section set according to the above.
def get_part_chapter_section(cols, reqt, options):
    if reqt[PART] is None:
        return [reqt]

    reqts = []
    col_idx = int(reqt[PART])
    temp = cleanup_text(cols[col_idx])
    part_chap_secs = temp.split("Part ")
    for pcs_line in part_chap_secs:
        if pcs_line == '':
            continue
        pcs = pcs_line.split(',')
        reqt[PART] = pcs[0].strip()
        reqt[SECTION] = pcs[1].strip()
        sections = reqt[SECTION].split('.')
        reqt[CHAPTER] = "Chapter " + sections[1].strip()
        reqts.append(copy.copy(reqt))
    return reqts

# Parse_row returns a list requirements.
# Each requirement is a dict with the following keys:
# - Specification Revision
# - Specification Part number
# - Chapter number
# - Section number
# - requirement/recommendation
# - Requirement text
# - Checklist Identifier
#
# If multiple specification references apply to the requirement,
# one requirement is returned for each specification reference.

def parse_row(row, options):
    global REQTS
    TABLE_COLUMN = r"<TD"

    if not row.find(TABLE_COLUMN):
        return None

    reqt = copy.copy(REQTS)
    reqt[REVISION] = options.revision_number
    cols = row.split(TABLE_COLUMN)
    reqt = get_checklist_item_and_sentence(cols, reqt, options)
    reqts = get_part_chapter_section(cols, reqt, options)
 
    return reqts

def parse_checklist(options):
    reqts = []
    checklist_file = open(options.filename_of_checklist)
    checklist = checklist_file.read()
    checklist_file.close()

    table_rows = checklist.split("<TR>")
    print "Row count", len(table_rows)
    for row in table_rows:
        new_reqts = parse_row(row, options)
        if new_reqts is not None:
            for reqt in new_reqts:
                if reqt is None:
                    continue
                if reqt[CHAPTER] is None and reqt[CHKLIST_ID] is None:
                    if reqt[SENTENCE] is not None:
                        print "Appending reqt to previous"
                        reqts[-1][SENTENCE] += reqt[SENTENCE]
                else:
                    reqts.append(reqt)
        sys.stdout.flush()
    return reqts

def print_reqts(reqts):
    print "Revision, Part, Chapter, Section, Type, Sentence"
    for reqt in reqts:
        print reqt

def main(argv = None):
    parser = create_parser()
    if argv is None:
        argv = sys.argv[1:]

    (options, argv) = parser.parse_args(argv)
    if len(argv) != 0:
        print 'Invalid argument!'
        print
        parser.print_help()
        return -1

    options = validate_options(options)

    reqts = parse_checklist(options)

    if len(reqts) == 0:
        print "No requirements found"
        return 0

    print_reqts(reqts)

if __name__ == '__main__':
    sys.exit(main())
