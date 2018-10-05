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

class ChecklistRequirement(object):
    def __init__(self, filename=None, part_number=None, rev=None):
        self.sentence = None
        self.sentence_num = 1000
        self.reqt_type = None
        self.revision = rev
        self.part = part_number
        self.chapter = None
        self.section = None
        self.checklist_file = filename
        self.table_name = None
        self.chklist_id = None
        self.optional = "STANDARD"

    def __str__(self):
        return ("'%s' '%s' '%s' '%s' '%s' '%s' '%s' '%s' '%s' '%s'" %
               (self.sentence, self.reqt_type, self.revision, self.part,
                self.chapter, self.section, self.checklist_file,
                self.table_name, self.chklist_id, self.optional))

class ChecklistParser(object):
    TYPE_RECOMMENDATION = "Recommendation"
    TYPE_REQUIREMENT = "REQUIREMENT"
    ITEM_PREFIX = "Item "

    TABLE_ROW = "<TR>"
    TABLE_COLUMN = "<TD>"
    SECTION_NUMBER =  r"(\d+\.\d+[\.\d+]*)"

    def __init__(self, checklist_filename,
                       optional_filename = None,
                       part_number=None,
                       revision=None,
                       rev2_part6=False):
        SUBITEM_RE =  r"([0-9]+[A-Z][0-9]*).* DETAIL: "
        SUBITEM_ID =  r"([0-9]+[A-Z][0-9]*)"
        CHKLIST_RE = r"([0-9]+\.)"

        self.rev2_part6 = rev2_part6
        self.default_reqt = ChecklistRequirement(filename=checklist_filename,
                                                rev=revision,
                                           part_number = "Part " + part_number)
        self.saved_refs = None
        self.part_chapter_section_col = None
        self.reqts = []
        self.sentence_num = 1000

        self.checklist_pattern = re.compile(CHKLIST_RE)
        self.subitem_pattern = re.compile(SUBITEM_RE,
                                          flags=re.IGNORECASE | re.VERBOSE)
        self.subitem_identifier = re.compile(SUBITEM_ID)
        self.section_number = re.compile(self.SECTION_NUMBER,
                                          flags=re.IGNORECASE | re.VERBOSE)

        checklist_file = open(checklist_filename)
        self.checklist = checklist_file.read()
        checklist_file.close()

        self.optionslist = []
        self.optional_table_items_fn = None
        if optional_filename is not None:
            self.optional_table_items_fn = optional_filename
            options_file = open(optional_filename)
            self.optionslist = [t.strip() for t in options_file.readlines()]
            options_file.close()

        self.setup_options()
        self.parse_checklist()

    def setup_options(self):
        self.optional_table_items = []
        for line_num, line in enumerate(self.optionslist):
            tokens = [re.sub("'", "", tok) for tok in line.split("', ")]
            token_str = "'" + "', '".join(tokens) + "'"
            if not len(tokens) == 3:
                logging.warn("File '%s' Line %d: 3 tokens expected, got %d: %s"
                         % (self.optional_table_items_fn, line_num,
                            len(tokens), token_str))
                continue
            logging.info("Optional: %s" % token_str)
            self.optional_table_items.append(tokens)
        

    def parse_checklist(self):
        # substitution below is due to some nasty characters
        # in a few checklists...
        self.checklist = re.sub("\xc2\xa0", " ", self.checklist)
        self.checklist = re.sub("\xe2\x80\xa2", " ", self.checklist)
        self.tables = self.checklist.split("<Table>")
        self.default_reqt.table_name = None
        for table in self.tables:
            logging.debug("Split table: %s" % table[0:100])
            self.parse_table(table)

    # Remove all XML and other extraneous characters/expressions in the text
    @staticmethod
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
        text = re.sub('&#8226;', '', text)
        text = re.sub('&#8221;', '"', text)
        text = re.sub('&#8220;', '"', text)
        text = re.sub('&#8216;', "'", text)
        text = re.sub('&#8217;', "'", text)
        text = re.sub('&quot;', '"', text)
        text = re.sub('&gt;', '>', text)
        text = re.sub('&lt;', '<', text)

        # Correct some spelling/grammatical errors in original tables.
        # Problem in 1.3 Error Management Checklist Table 2 items 12F,
        # 12G, and 12I
        text = re.sub('an packet', 'a packet', text)
        # Problem in 1.3 Error Management Checklist Table 2 item 20C
        text = re.sub('APort', 'A Port', text)
        # Conversion to ASCII removes the S-overbar notation in the
        # 1.3 Error Management Checklist Table 2-12 items 1C3 and 1C4.
        # This attempts to correct that.
        text = re.sub('ackID, S, S, or rsrv', 'ackID, S, S-overbar, or rsrv', text)
        text = re.sub('ackID, S, S, and rsrv', 'ackID, S, S-overbar, and rsrv', text)
        # The only reference in 1.3 Error Management Checklist Table 2-13
        # item 6 is to the previous table 2-12.  Change that to refer to the
        # correct specification section.
        text = re.sub('Table 2-12 above', 'Part 4, Sec. 2.4.5', text)

        return text.strip()

    def check_sentence_for_subitem_pattern(self, sentence,
                                           part_chapter_section_col):
        result = self.subitem_pattern.match(sentence)
        if not result:
            logging.debug("        NO SUBITEM")
            return False

        logging.debug("        SUBITEM_RE: '%s'" % result.group(0))
        temp = self.subitem_identifier.match(result.group(0))
        self.reqt.chklist_id = self.ITEM_PREFIX + temp.group(0)
        logging.debug("        SUBITEM_ID: '%s'" % temp.group(0))
        sentence_start = len(result.group(0))
        self.reqt.sentence = self.cleanup_text(sentence[sentence_start:])
        self.reqt.reqt_type = "REQUIREMENT"
        self.part_chapter_section_col = part_chapter_section_col
        return True

    # get_checklist_item_and_sentence
    #
    # Parses the first non-empty column, looking for one of the following
    # patterns:
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
    # Note: in the Error Management Checklist.xml, it is possible to have
    #       both an (A) item identifier and a sentence that starts with
    #       (C) in an XML table row.  In this case, the item identifer
    #       used is (C)

    def get_checklist_item_and_sentence(self):
        ITEM_CHKLIST = "ITEM "

        logging.debug("    columns[0]: '%s'" % self.columns[0])
        if self.columns[0].startswith(ITEM_CHKLIST):
            logging.debug("    ITEM")
            colon = self.columns[0].find(":")
            if colon > 0:
                self.reqt.chklist_id = (self.ITEM_PREFIX
                                     + self.columns[0][len(ITEM_CHKLIST):colon].strip())
                self.reqt.sentence = self.columns[0][colon + 1:].strip()
                self.reqt.reqt_type = "REQUIREMENT"
                self.part_chapter_section_col = 1
                logging.debug("    Reqt: %s" % self.reqt)
            else:
                logging.debug("    No colon...")
        else:
            logging.debug("    No ITEM")

        result = self.checklist_pattern.match(self.columns[0])
        if result:
            logging.debug("    NUMBER")
            self.reqt.chklist_id = (self.ITEM_PREFIX
                                  + result.group(0)[:-1].strip())
            self.reqt.sentence = self.columns[1]
            self.reqt.reqt_type = "REQUIREMENT"
            self.part_chapter_section_col = 2
            logging.debug("    Reqt B4: %s" % self.reqt)
            self.check_sentence_for_subitem_pattern(self.reqt.sentence, 2)
            logging.debug("    Reqt: %s" % self.reqt)
            return

        logging.debug("    No NUMBER")
        self.check_sentence_for_subitem_pattern(self.columns[0], 1)
        logging.debug("    Reqt: %s" % self.reqt)

    def add_requirement(self):
        self.table_name = None
        self.chklist_id = None
        self.optional = "STANDARD"
        chk_tuple = [self.reqt.table_name, self.reqt.chklist_id, "OPTIONAL"]
        if (chk_tuple in self.optional_table_items):
            self.reqt.optional = "OPTIONAL"
        self.reqt.sentence_num = self.sentence_num
        self.sentence_num += 1
        self.reqts.append(copy.deepcopy(self.reqt))
        self.reqt.optional = "STANDARD"

    # Parse first column which has one or more lines of the form:
    # Part X, Sec. Chapter.Y.Z...
    # Part X, Sec.Chapter.Y.Z...
    # Adds one requirement for each line, with
    # part, chapter, and section set according to the above.
    def add_one_requirement_per_reference(self):
        logging.debug("Adding one requirement per reference...")
        if self.part_chapter_section_col is None:
            logging.debug("part_chapter_section_col is none, skipping...")
            return

        temp = self.cleanup_text(self.columns[self.part_chapter_section_col])
        logging.debug("        Raw cols: %s" % temp)
        # Jiggerey pokery required for Rev 1.3 checklist.
        #
        # When references in the original document are in a "merged" table cell,
        # the references in the XML are only in the first table row.  The merged
        # table cell can span multiple XML <Table> instances.
        #
        # In Rev 1.3 Table 3-16 Item 6B the reference pulls in the subsequent
        # Chapter 4 chapter heading text.  This is detected and overridden
        # by the length check.
        if temp.find("Part") >= 0 and len(temp) < 200:
            logging.debug("        Saving references: '%s'" % temp)
            self.saved_refs = temp
        else:
            temp = self.saved_refs
            logging.debug("        Using saved refs: '%s'" % temp)
        if temp is None:
            logging.debug("        No refs, skipping...'")
            return

        part_chap_secs = temp.split("Part ")
        logging.debug("Extracting reference from: '%s'" % temp)
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
            self.reqt.part = "Part " + pcs[0].strip()

            result = self.section_number.search(pcs[1].strip())
            if result:
                self.reqt.section = result.group(0)
            else:
                self.reqt.section = pcs[1].strip()
            self.reqt.chapter = "Chapter " + sections[1][0]
            logging.debug("        Part: '%s' Chapter: '%s' Section: '%s'"
                      % (self.reqt.part, self.reqt.chapter, self.reqt.section))
            if (self.reqt.revision == "1.3"
                and self.reqt.part == "Part 6"
                and self.reqt.chapter == "Chapter 4"
                and (self.reqt.section == "Table 4-1"
                     or self.reqt.section == "Table 4-2")):
                logging.debug("        Skipping table references...")
                continue
            # Skip erroneous requirement reference found in
            # rev1.3 Checklists, Table 2-4, item 12A/A1/A2.
            # This should be a references to Part 4, which is not
            # supported by the checklists.
            if (self.reqt.revision == "1.3"
                and self.reqt.part == "Part 6"
                and self.reqt.section == "5.8.2.1"):
                    continue
            # Correct erroneous requirement reference found in
            # rev1.3 Checklists, Table 3-8, item 12
            if (self.reqt.revision == "1.3"
                and self.reqt.part == "Part 1"
                and self.reqt.chapter == "Chapter 2"
                and (self.reqt.section == "2.32.2")):
                self.reqt.section = "2.3.2.2"
            # Correct erroneous requirement reference found in
            # rev1.3 Checklists, Table 3-12, item 1A, 1B
            if (self.reqt.revision == "1.3"
               and self.reqt.part == "Part 6"
               and self.reqt.chapter == "Chapter 5"
               and self.reqt.section == "5.10.2.3.2"):
                    self.reqt.section = "5.11.2.3.2"
                # Correct erroneous requirement reference found in
                # rev1.3 Checklists, Table 4-1, item 2G
            if (self.reqt.revision == "1.3"
                and self.reqt.part == "Part 3"
                and self.reqt.chapter == "Chapter 2"
                and self.reqt.section == "2.3.1"):
                    self.reqt.chapter = "Chapter 3"
                    self.reqt.section = "3.4.1"
                # Correct erroneous requirement reference found in
                # rev1.3 Checklists, Table 6-4, item 3.
            if (self.reqt.revision == "1.3"
                and self.reqt.part == "Part 1"
                and self.reqt.chapter == "Chapter 3"
                and self.reqt.section == "3.41"):
                    self.reqt.section = "3.4.1"
            self.add_requirement()

    def rev2_part6_get_cols_from_row(self, row):
        temp = [col.strip() for col in row.split(self.TABLE_COLUMN)]
        self.columns = []
        for t in temp:
            col = self.cleanup_text(t)
            if not col == "":
               self.columns.append(col)
        logging.debug("Rev2_Part6_Columns: %s" % self.columns)

    def rev2_part6_add_requirements(self):
        REV2p6_TABLE_ITEM = self.SECTION_NUMBER + "[A-Z][\.\d+]*"
        table_item = re.compile(REV2p6_TABLE_ITEM)

        result = table_item.match(self.columns[0])
        if not result:
            return
        self.reqt = copy.deepcopy(self.default_reqt)
        self.reqt.chklist_id = result.group(0)
        section = self.section_number.match(self.reqt.chklist_id)
        if not section:
            logging.error("Found ID, no section: '%s'" % self.reqt.chklist_id)
            return
        self.reqt.section = section.group(0)
        if self.reqt.section[-1] == ".":
            self.reqt.section = self.reqt.section[:-1]
        self.reqt.sentence = self.columns[1]
        self.reqt.reqt_type = self.TYPE_REQUIREMENT
        self.reqt.chklist_id = self.ITEM_PREFIX + self.reqt.chklist_id
        logging.info("Table REQT: '%s': '%s'"
                   % (self.reqt.chklist_id, self.reqt.table_name))
        self.add_requirement()

    def rev2_part6_parse_table(self):
        TABLE_NUMBER = r"\d+"

        table_number_re = re.compile(TABLE_NUMBER)

        new_reqts = []
        self.rows = self.table.split(self.TABLE_ROW)
        self.default_reqt.table_name = None

        for row in self.rows:
            self.rev2_part6_get_cols_from_row(row)
            if len(self.columns) < 2:
                logging.info("Skipping Row: '%s'" % row[0:50])
                continue
            if self.default_reqt.table_name is None:
                result =  table_number_re.match(self.columns[0])
                if not result:
                    logging.info("No Number Row: '%s'" % row[0:50])
                    continue
                self.default_reqt.chapter = "Chapter %s" % result.group(0)
                self.default_reqt.table_name = ("Table %s %s"
                                             % (result.group(0), self.columns[1]))
                logging.info("Table: '%s'" % self.default_reqt.table_name)
                continue
            # Know the table name, now get requirements...
            self.rev2_part6_add_requirements()

    def parse_table_name(self):
        TABLE_TITLE = "<TableTitle>"
        TABLE_TITLE_END = "</TableTitle>"
        CAPTION = "<Caption>"
        CAPTION_END = "</Caption>"

        new_table_name = None
        DELIMITERS = [[TABLE_TITLE, TABLE_TITLE_END],
                      [    CAPTION, CAPTION_END    ]]
        for delim in DELIMITERS:
            start = self.table.find(delim[0])
            end = self.table.find(delim[1])
            if start < 0 or end < 0:
                continue
            new_table_name = self.table[start:end]
            logging.debug("Raw table name: '%s'" % new_table_name)
            new_table_name = self.cleanup_text(new_table_name)
            logging.debug("Clean table name: '%s'" % new_table_name)
            self.table = self.table[end + len(delim[1]):]
            break

        if new_table_name is None:
            logging.debug("Table name not found in %s" % self.table[0:50])
            return

        logging.debug("Table name: %s" % new_table_name)
        self.default_reqt.table_name = new_table_name
        self.saved_refs = None

    def parse_usual_table(self):
        new_table_name = None

        if self.default_reqt.table_name is None:
            logging.info("No table name, skipping %s" % self.table[0:50])
            return

        logging.info("Table Name: '%s'" % self.default_reqt.table_name)
        self.rows = self.table.split(self.TABLE_ROW)
        for row in self.rows:
            items = [col.strip() for col in row.split(self.TABLE_COLUMN)]
            self.columns = []
            for item in items:
                temp = self.cleanup_text(item)
                if not temp == "":
                    self.columns.append(temp)
            if not self.columns:
                logging.debug("Skipping row: %s" % row)
                continue
            logging.debug("columns: %s" % self.columns)
            sys.stdout.flush()
            self.reqt = copy.deepcopy(self.default_reqt)
            self.get_checklist_item_and_sentence()
            if self.reqt.sentence is None:
                logging.debug("No sentence, skipping...")
                continue
            # Skip item duplicated in original 1.3 checklists.
            if self.reqt.table_name == 'Table 6-3. General device message passing logical layer source transaction support list' and self.reqt.chklist_id == '1C':
                continue
            self.add_one_requirement_per_reference()

    def parse_table(self, table):
        self.table = table

        if self.rev2_part6:
            self.rev2_part6_parse_table()
        else:
            self.parse_table_name()
            self.parse_usual_table()

    def print_reqts(self):
        if len(self.reqts) == 0:
            print "No requirements found"

        print "Sentence, Sentence_num, Type, Revision, Part, Chapter, Section, FileName, Table_Name, Checklist_ID, Optional"
        for reqt in self.reqts:
            print ("'%s', '%d', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s', '%s'"
                % (reqt.sentence, reqt.sentence_num, reqt.reqt_type, reqt.revision, reqt.part,
                   reqt.chapter, reqt.section,
                   reqt.checklist_file, reqt.table_name, reqt.chklist_id,
                   reqt.optional))

def create_parser():
    parser = OptionParser()
    parser.add_option('-f', '--file',
            dest = 'checklist_filename',
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
            metavar = 'REV')
    parser.add_option('-o', '--optional',
            dest = 'optional',
            action = 'store', type = 'string', default=None,
            help = 'File containing table name and item for optional requirements.',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if options.checklist_filename is None:
        print "Must enter file name of checklist."
        sys.exit()

    if not os.path.isfile(options.checklist_filename):
        print ("File %s not found." % options.checklist_filename)
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

    if options.optional is not None:
        if not os.path.isfile(options.optional):
            print "File '%s' not found" % options.optional
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
    parser = ChecklistParser(checklist_filename = options.checklist_filename,
                             optional_filename = options.optional,
                             revision = options.revision_number,
                             part_number = options.part_number,
                             rev2_part6 = options.rev_2_part_6)
    parser.print_reqts()

if __name__ == '__main__':
    sys.exit(main())
