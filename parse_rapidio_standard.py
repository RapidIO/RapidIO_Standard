#!/usr/bin/env python
# -*- coding: latin-1 -*-
"""
    Parse the RapidIO 4.0 standard, saved in XML format.

    Creates schema based on:
    Part Number (1-13)
    Chapter Number (H2)
    Section Number (H3-H6)
    Type (Requirement, Recommendation)
    Sentence
    - Requirement (all sentences containing "shall" or "must") or
    - Recommendation (all sentences containing "should", "recommend")

"""

from optparse import OptionParser
import re
import sys
import os
import logging

class RequirementFields(object):
    REVISION = "Revision"
    PART = "Part"
    CHAPTER = "Chapter"
    SECTION = "Section"
    TYPE = "TYPE"
    SENTENCE = "Sentence"

class RapidIOStandardParser(object):
    REQTS = {RequirementFields.REVISION:0,
             RequirementFields.PART:1,
             RequirementFields.CHAPTER:2,
             RequirementFields.SECTION:3,
             RequirementFields.TYPE:4,
             RequirementFields.SENTENCE:5}

    TYPE_RECOMMENDATION = "Recommendation"
    TYPE_REQUIREMENT = "REQUIREMENT"

    def __init__(self, std_xml_file, target_part=None):
        self.input_xml = std_xml_file
        self.target_part = target_part
        self.target_number = None
        self.part_number = None

    # Sneaky: Remove XML but replace tags with periods.
    # This may result in many empty sentences, but it also results
    # in ignoring a lot of figure/table titles, headers, etc...
    @staticmethod
    def remove_xml(text):
        return re.sub(r'\<[^>]+\>', " . ", text)

    @staticmethod
    def remove_number_prefix(s):
        if s[0] >= '0' and s[0] <= '9':
            return RapidIOStandardParser.remove_number_prefix(s[1:])
        return s

    # split_into_sentences and the constants below were adapted from code at
    # https://stackoverflow.com/questions/4576077/python-split-text-on-sentences
    def split_into_sentences(self, text):
        CAPS = "([A-Z])"
        PREFIXES = "(Mr|St|Mrs|Ms|Dr)[.]"
        SUFFIXES = "(Inc|Ltd|Jr|Sr|Co)"
        STARTERS = "(Mr|Mrs|Ms|Dr|He\s|She\s|It\s|They\s|Their\s|Our\s|We\s|But\s|However\s|That\s|This\s|Wherever)"
        ACRONYMS = "([A-Z][.][A-Z][.](?:[A-Z][.])?)"
        WEBSITES = "[.](com|net|org|io|gov)"
        DIGITS = "([0-9])"

        text = re.sub(PREFIXES,"\\1<prd>",text)
        text = re.sub(r"\.\.+",r"<ellipsis>",text)
        text = re.sub(WEBSITES,"<prd>\\1",text)
        text = re.sub(DIGITS + "[.]" + DIGITS,"\\1<prd>\\2",text)
        if "Ph.D" in text: text = text.replace("Ph.D.","Ph<prd>D<prd>")
        text = re.sub("\s" + CAPS + "[.] "," \\1<prd> ",text)
        text = re.sub(ACRONYMS+" "+STARTERS,"\\1<stop> \\2",text)
        text = re.sub(CAPS + "[.]" + CAPS + "[.]" + CAPS + "[.]","\\1<prd>\\2<prd>\\3<prd>",text)
        text = re.sub(CAPS + "[.]" + CAPS + "[.]","\\1<prd>\\2<prd>",text)
        text = re.sub(" "+SUFFIXES+"[.] "+STARTERS," \\1<stop> \\2",text)
        text = re.sub(" "+SUFFIXES+"[.]"," \\1<prd>",text)
        text = re.sub(" " + CAPS + "[.]"," \\1<prd>",text)
        if '"' in text: text = text.replace('"',"<quote>")
        if "!" in text: text = text.replace("!\"","\"!")
        if "?" in text: text = text.replace("?\"","\"?")
        text = text.replace(".",".<stop>")
        text = text.replace("?","?<stop>")
        text = text.replace("!","!<stop>")
        text = text.replace("<prd>",".")
        self.sentences = text.split("<stop>")
        self.sentences = self.sentences[:-1]
        self.sentences = [s.strip() for s in self.sentences]
        self.sentences = [self.remove_number_prefix(s) for s in self.sentences]

    def parse_sections(self):
        REQT_KW = ["must", "shall", "Do not depend"]
        REC_KW = ["should", "recommend"]
        SECTION_END = "</"

        self.section_name = self.chapter_name

        for sect in self.sections:
            heading_end = 0
            if sect[0] >= '0' and sect[0] <= '9':
                sect = self.section_number + sect
                heading_end = sect.find(SECTION_END)
                temp = sect[:heading_end].strip()
                tokens = temp.split(' ')
                if len(tokens) > 1 and (tokens[0][-1] >= '0' and tokens[0][-1] <= '9'):
                    self.section_name = temp
                    logging.debug("section_name :" + self.section_name)
            sect = self.remove_xml(sect)
            self.split_into_sentences(sect[heading_end + len(SECTION_END):])
            for s in self.sentences:
                s_type = None
                if any(sub in s for sub in REQT_KW):
                    s_type = self.TYPE_REQUIREMENT;
                elif any(sub in s for sub in REC_KW):
                    s_type = self.TYPE_RECOMMENDATION;
                if s_type is None:
                    continue
                new_reqt = [None] * (max(self.REQTS.values()) + 1)
                new_reqt[self.REQTS[RequirementFields.REVISION]] = "4.0"
                new_reqt[self.REQTS[RequirementFields.PART]] = self.part_name
                new_reqt[self.REQTS[RequirementFields.CHAPTER]] = self.chapter_name
                new_reqt[self.REQTS[RequirementFields.SECTION]] = self.section_name
                new_reqt[self.REQTS[RequirementFields.TYPE]] = s_type
                new_reqt[self.REQTS[RequirementFields.SENTENCE]] = s
                self.reqts.append(new_reqt)

    def parse_chapters(self):
        CH_END = r"</"

        self.chapter_number = None
        self.section_number = None
        self.section_prefix = None
        for chapter in self.chapters:
            chapter = "Chapter " + chapter
            end_idx = chapter.find(CH_END)
            new_chapter_name = chapter[:end_idx].strip()
            end_idx += len(CH_END)
            end_idx += chapter[end_idx:].find('>') + len('>')
            chapter_number_found = re.search(r"Chapter ([0-9]*) ", new_chapter_name)
            if chapter_number_found:
                self.chapter_number = chapter_number_found.group(1).strip()
                self.chapter_name = new_chapter_name
                logging.debug("chapter_name: '" + self.chapter_name + "'")
            if self.chapter_number is None:
                logging.debug("No chapter number found yet, skipping " + chapter)
                continue
            self.section_number = self.chapter_number + "."
            self.section_prefix = r">" + self.chapter_number + r"."
            self.sections = chapter[end_idx:].split(self.section_prefix)
            self.parse_sections()

    def print_reqts(self):
        if len(self.reqts) == 0:
            print "No requirements found for " + self.part_num
            return 0

        print "Revision, Part, Chapter, Section, Type, Sentence"
        for reqt in self.reqts:
            print reqt

    # Perform character substitutions to simplify parsing of text and correct
    # some text conversion errors...
    def condition_all_text(self):
        self.all_text = re.sub('\n', ' ', self.all_text)
        self.all_text = re.sub('\t', '', self.all_text)
        self.all_text = re.sub('\r', ' ', self.all_text)
        self.all_text = re.sub('™', '', self.all_text)
        self.all_text = re.sub('•', '', self.all_text)
        self.all_text = re.sub("“", '"', self.all_text)
        self.all_text = re.sub("”", '"', self.all_text)
        self.all_text = re.sub("’", "'", self.all_text)
        self.all_text = re.sub('LogicalSpecification', 'Logical Specification', self.all_text)
        self.all_text = re.sub('SpecificationPart', 'Specification Part', self.all_text)
        self.all_text = re.sub('PhysicalLayer', 'Physical Layer', self.all_text)
        self.all_text = re.sub('DeviceInter-operability', 'Device Inter-operability', self.all_text)
        self.all_text = re.sub('4.2.7 Type 3–4 Packet Formats \(Reserved\)',
                      '<P>4.2.7 Type 3–4 Packet Formats (Reserved) </P>', self.all_text)
        self.all_text = re.sub('4.2.8 Type 5 Packet Format \(Write Class\)',
                      '<P>4.2.8 Type 5 Packet Format (Write Class) </P>', self.all_text)
        self.all_text = re.sub('RapidIOTM', 'RapidIO', self.all_text)
        self.all_text = re.sub('3.0, 10/2013 © Copyright RapidIO.org ', '', self.all_text)
        self.all_text = re.sub('[0-9+] RapidIO.org', '', self.all_text)
        self.all_text = re.sub('RapidIO.org [0-9+]', '', self.all_text)
        self.all_text = re.sub(r" id=\"LinkTarget_[0-9]*\">", r'>',  self.all_text)

    # Work around embedded specification part references in
    # Version 4.0, Part 10 Chapter 5
    def fixup_parts(self):
        new_parts = []
        for part in self.parts:
            chapter_number_found = re.search(r"Chapter ([0-9]*) ", part)
            if chapter_number_found:
                new_parts.append(part)
            else:
                if len(new_parts) > 0:
                   new_parts[-1] += part
        self.parts = new_parts

    def parse_parts(self):
        part_header = "RapidIO Interconnect Specification "
        annex = "Annex"
        self.reqts = []
    
        target_number = None
        target_is_annex = None
    
        found_number = re.search(" ([0-9]*)", self.target_part)
        if found_number:
            self.target_number = int(found_number.group(1))
            self.target_is_annex = self.part_num.find(annex) >= 0
            logging.debug("target_number " + self.target_number)
            logging.debug("target_is_annex " + self.target_is_annex)
    
        spec_file = open(self.input_xml)
        self.all_text = spec_file.read()
        spec_file.close()
    
        self.all_text = " " + self.all_text + "  "
        self.condition_all_text()
        self.parts = self.all_text.split( ">" + part_header)
        self.fixup_parts()
        self.part_name = ''
        self.part_number = ''
        self.part_annex = False
        for part in self.parts:
            part = part_header + part
            new_part_name = part[:part.find('<')]
            # Jiggery pokery below is required to weed out references to
            # specification parts found within other parts of the specification.
            # This is dependent on all of these references always being backward
            # i.e. Part 10 can refer to Part 1, but Part 1 cannot refer to Part 10
            # This dependency is true up to Revision 4.0.
            found_number = re.search(" ([0-9]*):", new_part_name)
            if found_number:
                new_part_number = int(found_number.group(1))
                new_part_annex = new_part_name.find("Annex") >= 0
                if (self.part_name == ''
                    or (new_part_annex and not self.part_annex)
                    or (not (new_part_annex ^ self.part_annex)
                        and (new_part_number > self.part_number))):
                    self.part_name = new_part_name
                    self.part_number = new_part_number
                    self.part_annex = new_part_annex
                    logging.debug("part_name: " + self.part_name +
                                  " number " + str(self.part_number) +
                                  " annex " + str(self.part_annex))
    
            if self.target_number is not None:
                if self.part_number is None or self.part_number == '':
                    continue
                sys.stdout.flush()
                if ((not int(self.part_number) == int(self.target_number))
                    or not (self.target_is_annex == self.part_annex)):
                    continue
            self.chapters = part[len(new_part_name):].split('>Chapter ')
            self.parse_chapters()

def create_parser():
    parser = OptionParser()
    parser.add_option('-f', '--file',
            dest = 'filename_of_standard',
            action = 'store', type = 'string',
            help = 'RapidIO Specification Stack in XML format.',
            metavar = 'FILE')
    parser.add_option('-p', '--part',
            dest = 'target_part',
            action = 'store', type = 'string',
            help = '"Part ##" or "Annex #".  Default is all.',
            metavar = 'FILE')
    return parser

def validate_options(options):
    if options.filename_of_standard is None:
        print "Must enter file name of standard."
        sys.exit()

    if not os.path.isfile(options.filename_of_standard):
        print "File '" + options.filename_of_standard +"' does not exist."
        sys.exit()

    if options.target_part is None:
        options.target_part = '*'
    return options

def main(argv = None):
    logging.basicConfig(level=logging.WARNING)
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

    std_parser = RapidIOStandardParser(options.filename_of_standard,
                                       options.target_part)
    std_parser.parse_parts()
    std_parser.print_reqts()

if __name__ == '__main__':
    sys.exit(main())
