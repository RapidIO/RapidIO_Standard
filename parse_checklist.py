#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Parse the Data Streaming checklist XML file

    Parses checklist and prints one line of output for each checklist item.
    Each line has the following content:
    - Sentence
    - Type (Requirement)
    - Revision (enterend by user)
    - Part Number (1-13)
    - Chapter Number
    - Section Number
    - Checklist file name
    - Checklist table name
    - Checklist item number
    Note that if there is more than one specification reference in the
    checklist, then one line of output is displayed for each specification
    reference.
"""

from optparse import OptionParser
import re
import sys
import os
import copy
import logging

PRINT_TRACE = False

REVISION = "Revision"
PART = "Part"
CHAPTER = "Chapter"
SECTION = "Section"
TYPE = "TYPE"
SENTENCE = "Sentence"
CHKLIST_FILE = "Checklist_File"
TABLE_NAME = "Table_Name"
CHKLIST_ID = "Checklist_ID"
COL = "Column"
SAVED_REFS = "Column"
REV2_PART6 = "Rev2_part6"

REQTS = {REVISION:None,
         PART:None,
         CHAPTER:None,
         SECTION:None,
         TYPE:None,
         SENTENCE:None,
         CHKLIST_FILE:None,
         TABLE_NAME:None,
         CHKLIST_ID:None,
         COL:None,
         SAVED_REFS:None,
         REV2_PART6:False}

TYPE_RECOMMENDATION = "Recommendation"
TYPE_REQUIREMENT = "REQUIREMENT"

TABLE_ROW = "<TR>"
TABLE_COLUMN = "<TD>"
SECTION_NUMBER =  r"(\d+\.\d+[\.\d+]*)"

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

def make_id(chklist_id):
    return "Item " + chklist_id.strip()

def check_sentence_for_subitem_pattern(column, item_col, reqt):
    SUBITEM_RE =  r"([0-9]+[A-Z][0-9]*).* DETAIL: "
    SUBITEM_ID =  r"([0-9]+[A-Z][0-9]*)"

    subitem_pattern = re.compile(SUBITEM_RE, flags=re.IGNORECASE | re.VERBOSE)
    subitem_identifier = re.compile(SUBITEM_ID)
    result = subitem_pattern.match(column)
    if result:
        logging.debug("        SUBITEM_RE: '%s'" % result.group(0))
        temp = subitem_identifier.match(result.group(0))
        reqt[CHKLIST_ID] = temp.group(0)
        logging.debug("        SUBITEM_ID: '%s'" % temp.group(0))
        sentence_start = len(result.group(0))
        reqt[SENTENCE] = cleanup_text(column[sentence_start:])
        reqt[TYPE] = "REQUIREMENT"
        reqt[COL] = item_col
    else:
        logging.debug("        NO SUBITEM")
    return reqt

# Parses the first non-empty column, looking for one of the following patterns:
# (A) [0-9]*\. (digits 0-9, followed by a period)
#     In this case, the requirement sentence is found in the next column.
# (B) ITEM [0-9]+[A-Z][0-9]*: SENTENCE"
#     In this case, the requirement sentence is part of the checklist item.
# (C) [0-9]+[A-Z][0-9]*: Detail: SENTENCE
#
# The return is an updated requirement with the CHECKLIST_ID and SENTENCE
# updated based on the above.
#
# Additionally, the COL entry is updated with the column number which
# should have the specification reference
#
# Note: in the Error Management Checklist.xml, it is possible to have both an
# (A) item identifier and a sentence that starts with (C) in an XML table row.
# In this case, the item identifer should be (C)

def get_checklist_item_and_sentence(cols, reqt):
    ITEM_CHKLIST = "ITEM "
    CHKLIST_RE = r"([0-9]+\.)"
    checklist_pattern = re.compile(CHKLIST_RE)

    logging.debug("    cols[0]: '%s'" % cols[0])
    if cols[0].startswith(ITEM_CHKLIST):
        logging.debug("    ITEM")
        colon = cols[0].find(":")
        if colon > 0:
            x = make_id(cols[0][len(ITEM_CHKLIST):colon].strip())
            reqt[CHKLIST_ID] = x
            reqt[SENTENCE] = cols[0][colon + 1:].strip()
            reqt[TYPE] = "REQUIREMENT"
            reqt[COL] = 1
            logging.debug("    Reqt: %s" % reqt)
            return reqt
        else:
            logging.debug("    No colon...")
    else:
        logging.debug("    No ITEM")

    result = checklist_pattern.match(cols[0])
    if result:
        logging.debug("    NUMBER")
        x = make_id(result.group(0)[:-1].strip())
        reqt[CHKLIST_ID] = x
        reqt[SENTENCE] = cols[1]
        reqt[TYPE] = "REQUIREMENT"
        reqt[COL] = 2
        logging.debug("    Reqt B4: %s" % reqt)
        reqt = check_sentence_for_subitem_pattern(reqt[SENTENCE], 2, reqt)
        logging.debug("    Reqt: %s" % reqt)
        return reqt
    else:
        logging.debug("    No NUMBER")

    reqt = check_sentence_for_subitem_pattern(cols[0], 1, reqt)
    logging.debug("    Reqt: %s" % reqt)
    return reqt

# Parse first column which has one or more lines of the form:
# Part X, Sec. Chapter.Y.Z...
# Part X, Sec.Chapter.Y.Z...
# Returns one requirement for each line, with the fields
# Part, Chapter, and Section set according to the above.
def get_part_chapter_section(cols, reqt):
    if reqt[COL] is None:
        return [reqt]

    reqts = []
    col_idx = int(reqt[COL])
    temp = cleanup_text(cols[col_idx])
    # Jiggerey pokery required for Rev 1.3 checklist.
    #
    # When references in the original document are in a "merged" table cell,
    # the references in the XML are only in the first table row.  The merged
    # table cell can span multiple XML <Table> instances.
    #
    # In Rev 1.3 Table 3-16 Item 6B where the reference pulls in the subsequent
    # Chapter 4 text.  This is detected and overridden by the length check.
    if temp.find("Part") >= 0 and len(temp) < 200:
        logging.debug("        Saving references: '%s'" % temp)
        REQTS[SAVED_REFS] = temp
    else:
        temp = REQTS[SAVED_REFS]
        logging.debug("        Using saved refs: '%s'" % temp)
    if temp is None:
        logging.debug("        No refs, skipping...'")
        return None
    part_chap_secs = temp.split("Part ")
    logging.debug("Extracting reference from: '%s'" % temp)
    section_re = re.compile(SECTION_NUMBER, flags=re.IGNORECASE | re.VERBOSE)
    for pcs_line in part_chap_secs:
        if pcs_line == '':
            logging.debug("        Line empty...")
            continue
        logging.debug("    Reference: '%s'" % pcs_line)
        pcs = [p.strip() for p in pcs_line.split(',')]
        if len(pcs) < 2:
            logging.debug("        No PCS...")
            continue
        sections = [tok.strip() for tok in pcs[1].strip().split(' ')]
        logging.debug("    B4 Sections: '%s'" % sections)
        if len(sections) == 1:
            # Some section references leave out the space.
            # Check that the reference starts with "Sec.",
            # and tack on the section number to sections list.
            if sections[0].startswith("Sec."):
                sections.append(sections[0][len("Sec."):].strip())
                sections[1] = sections[0][len("Sec."):].strip()
            # Some section references leave out the "Sec.".
            # Check that the reference starts with a digit,
            # and tack on the section number to the sections list.
            if sections[0][0] in "0123456789":
                sections.append(sections[0])
        logging.debug("    Sections: '%s'" % sections)
        if len(sections) < 2:
            logging.debug("        No Sections...")
            continue
        logging.debug("        PCS: '%s'" % pcs)
        reqt[PART] = "Part " + pcs[0].strip()

        result = section_re.search(pcs[1].strip())
        if result:
            reqt[SECTION] = result.group(0)
        else:
            reqt[SECTION] = pcs[1].strip()
        reqt[CHAPTER] = "Chapter " + sections[1][0]
        logging.debug("        Part: '%s' Chapter: '%s' Section: '%s'"
                      % (reqt[PART], reqt[CHAPTER], reqt[SECTION]))
        if (reqt[REVISION] == "1.3"
            and reqt[PART] == "Part 6"
            and reqt[CHAPTER] == "Chapter 4"
            and (reqt[SECTION] == "Table 4-1" or reqt[SECTION] == "Table 4-2")):
            logging.debug("        Skipping table references...")
            continue

        reqts.append(copy.copy(reqt))
    return reqts

def rev2_part6_parse_table(table):
    TABLE_NUMBER = r"\d+"
    REV2p6_TABLE_ITEM = SECTION_NUMBER + "[A-Z][\.\d+]*"

    table_number_re = re.compile(TABLE_NUMBER)
    section_number = re.compile(SECTION_NUMBER)
    table_item = re.compile(REV2p6_TABLE_ITEM)

    reqts = []
    rows = table.split(TABLE_ROW)
    REQTS[TABLE_NAME] = None

    for row in rows:
        temp = [col.strip() for col in row.split(TABLE_COLUMN)]
        columns = []
        for t in temp:
            col = cleanup_text(t)
            if not col == "":
               columns.append(col)
        logging.debug("Columns: %s" % columns)
        if len(columns) < 2:
            logging.info("Skipping Row: '%s'" % row[0:50])
            continue
        if REQTS[TABLE_NAME] is None:
            result =  table_number_re.match(columns[0])
            if not result:
                logging.info("No Number Row: '%s'" % row[0:50])
                continue
            REQTS[CHAPTER] = "Chapter %s" % result.group(0)
            REQTS[TABLE_NAME] = "Table %s %s " % (result.group(0), columns[1])
            logging.info("Table: '%s'" % REQTS[TABLE_NAME])
            continue
        # Know the table name, now get requirements...
        reqt = copy.deepcopy(REQTS)
        result = table_item.match(columns[0])
        if result:
            reqt[CHKLIST_ID] = result.group(0)
            section = section_number.match(reqt[CHKLIST_ID])
            if not section:
                logging.error("Found ID but no section: '%s'" % reqt[CHKLIST_ID])
                continue
            reqt[SECTION] = section.group(0)
            if reqt[SECTION][-1] == ".":
                reqt[SECTION] = reqt[SECTION][:-1]
            reqt[SENTENCE] = columns[1]
            reqt[TYPE] = TYPE_REQUIREMENT
            logging.info("Table REQT: '%s': '%s'"
                       % (reqt[CHKLIST_ID], reqt[TABLE_NAME]))
            reqts.append(reqt)
    return reqts, None

def parse_table_name(table):
    TABLE_TITLE = "<TableTitle>"
    TABLE_TITLE_END = "</TableTitle>"
    CAPTION = "<Caption>"
    CAPTION_END = "</Caption>"

    new_table_name = None
    DELIMITERS = [[TABLE_TITLE, TABLE_TITLE_END],
                  [    CAPTION, CAPTION_END    ]]
    for delim in DELIMITERS:
        start = table.find(delim[0])
        end = table.find(delim[1])
        if start < 0 or end < 0:
            continue
        new_table_name = table[start:end]
        logging.debug("Raw table name: '%s'" % new_table_name)
        new_table_name = cleanup_text(new_table_name)
        logging.debug("Clean table name: '%s'" % new_table_name)
        table = table[end + len(delim[1]):]
        break
    if new_table_name is None:
        logging.debug("Table name not found in %s" % table[0:50])
    else:
        logging.debug("Table name: %s" % new_table_name)
    return table, new_table_name

def parse_table(table, table_name):
    global REQTS
    new_table_name = None
    reqts = []

    if REQTS[REV2_PART6]:
        return rev2_part6_parse_table(table)

    table, new_table_name = parse_table_name(table)
    if new_table_name is not None:
        logging.debug("New Table Name: %s" % new_table_name)
        table_name = new_table_name
        REQTS[SAVED_REFS] = None

    if table_name is None:
        logging.info("No table name, skipping %s" % table[0:50])
        return reqts, table_name

    REQTS[TABLE_NAME] = table_name
    logging.info("Table Name: '%s'" % table_name)
    rows = table.split(TABLE_ROW)
    for row in rows:
        items = [col.strip() for col in row.split(TABLE_COLUMN)]
        columns = []
        for item in items:
            temp = cleanup_text(item)
            if not temp == "":
                columns.append(temp)
        if not columns:
            logging.debug("Skipping row: %s" % row)
            continue
        logging.debug("columns: %s" % columns)
        reqt = copy.deepcopy(REQTS)
        reqt = get_checklist_item_and_sentence(columns, reqt)
        if reqt[SENTENCE] is None:
            logging.debug("No sentence, skipping...")
            continue
        new_reqts = get_part_chapter_section(columns, reqt)
        if new_reqts is not None:
            reqts += new_reqts

    return reqts, table_name

def parse_checklist(options):
    reqts = []
    checklist_file = open(options.filename_of_checklist)
    checklist = checklist_file.read()
    checklist_file.close()

    REQTS[CHKLIST_FILE] = options.filename_of_checklist
    REQTS[REVISION] = options.revision_number
    REQTS[PART] = "Part " + options.part_number
    REQTS[REV2_PART6] = options.rev_2_part_6

    # substitution below is due to some nasty characters in a few checklists...
    checklist = re.sub("\xc2\xa0", " ", checklist)
    checklist = re.sub("\xe2\x80\xa2", " ", checklist)
    tables = checklist.split("<Table>")
    table_name = None
    for table in tables:
        logging.debug("Split table: %s" % table[0:100])
        new_reqts, table_name = parse_table(table, table_name)
        if new_reqts is not None:
            reqts += new_reqts
    return reqts

def print_reqts(reqts):
    print "Sentence, Type, Revision, Part, Chapter, Section, FileName, Table_Name, Checklist_ID"
    for reqt in reqts:
        print ("'%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s'" %
              (reqt[SENTENCE], reqt[TYPE], reqt[REVISION], reqt[PART],
               reqt[CHAPTER], reqt[SECTION],
               reqt[CHKLIST_FILE], reqt[TABLE_NAME], reqt[CHKLIST_ID]))

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
    parser.add_option('-t', '--rev_two_part_six',
            dest = 'rev_2_part_6',
            action = 'store_true', default=False,
            help = 'Indicate that this is a rev2.2 part 6 checklist, which requires special parsing',
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

    options = validate_options(options)

    reqts = parse_checklist(options)

    if len(reqts) == 0:
        print "No requirements found"
        return 0

    print_reqts(reqts)

if __name__ == '__main__':
    sys.exit(main())
