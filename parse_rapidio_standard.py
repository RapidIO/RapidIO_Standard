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
from collections import OrderedDict
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

    def __init__(self, create_outline, std_xml_file, target_part=None, rev=None, new_secs=None):
        self.create_outline = create_outline
        self.outline = OrderedDict()
        self.input_xml = std_xml_file
        self.target_part = target_part
        self.target_number = None
        self.part_number = None
        self.new_secs = []
        if rev is None:
            self.revision = "Unknown"
            result = re.search("([0-9]\.[0-9])", self.input_xml)
            if result:
                self.revision = result.group(1)
        else:
            self.revision = rev
        self.read_new_secs(new_secs)

    def read_new_secs(self, new_secs):
        if new_secs is None:
            return
            
        new_secs_file = open(new_secs)
        new_secs_lines = [line.strip() for line in new_secs_file.readlines()]
        new_secs_file.close()

        for idx, line in enumerate(new_secs_lines):
            toks = [tok.strip() for tok in line[1:-1].split("', '")]
            if not len(toks) == 4:
                raise("New secs file %s line %d bad format: %s"
                    % (new_secs_file, idx, line))
            self.new_secs.append(toks[1:])

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
        if "Ph.D" in text:
           text = text.replace("Ph.D.","Ph<prd>D<prd>")
        text = re.sub("\s" + CAPS + "[.] "," \\1<prd> ",text)
        text = re.sub(ACRONYMS+" "+STARTERS,"\\1<stop> \\2",text)
        text = re.sub(CAPS + "[.]" + CAPS + "[.]" + CAPS + "[.]","\\1<prd>\\2<prd>\\3<prd>",text)
        text = re.sub(CAPS + "[.]" + CAPS + "[.]","\\1<prd>\\2<prd>",text)
        text = re.sub(" "+SUFFIXES+"[.] "+STARTERS," \\1<stop> \\2",text)
        text = re.sub(" "+SUFFIXES+"[.]"," \\1<prd>",text)
        text = re.sub(" " + CAPS + "[.]"," \\1<prd>",text)
        if '"' in text:
            text = text.replace('"',"<quote>")
        if "!" in text:
            text = text.replace("!\"","\"!")
        if "?" in text:
            text = text.replace("?\"","\"?")
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
                temp = re.sub("  +", " ", temp)
                temp = self.remove_xml(temp).strip()
                tokens = [tok.strip() for tok in temp.split(' ')]
                if len(tokens) > 1 and (tokens[0][-1] >= '0' and tokens[0][-1] <= '9'):
                    # If any lines have a unicode ellipsis "..." or a real
                    # ellipsis, assume that all sections are the "outline" of
                    # a chapter, and should be skipped.
                    if temp.find('\u2026') >= 0:
                        logging.debug("Section: '%s'" % sect)
                        logging.debug("Found unicode ellipsis, not parsing any more sections...")
                        return
                    # Skip lines with a sequence of periods "..." in them
                    # EXCEPT when the ellipsis is of the form used to indicate a range
                    # of register values...
                    if temp.find('.....') >= 0:
                        logging.debug("Section: '%s'" % sect)
                        logging.debug("Found long ellipsis, not parsing any more sections...")
                        return
                    # If the first token after the number does not start with a
                    # capital letter, it's not a real section name.
                    if len(tokens[1]) < 2:
                        logging.warn("Short Token1: '%s'" % tokens[1])
                        continue
                    if (tokens[1][0] in ('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')
                        or tokens[1][1] in ('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789')):
                        skip_outline = False
                        self.section_name = temp
                        logging.info("section_name :" + self.section_name)

                        # Skip misidentified heading in Revision 1.3, Part 6, Chapter 8
                        if (self.section_name == "8.0 Gb/s link"):
                            self.section_name = self.old_section
                            skip_outline = True

                        # Correct Rev 1.3 Part 11 Section 1.2/1.3 Requirements
                        if (self.part_name == "RapidIO Interconnect Specification Part 11: Multicast Extensions Specification"
                            and self.chapter_name == "Chapter 1 Overview"
                            and self.section_name == "1.2 Requirements"):
                            self.section_name = "1.3 Requirements"

                        # Correct Rev 2.2 Part 6 Section 6.6.10 parsing
                        if (self.section_name == "6.25 GBaud Support"
                            or self.section_name == "6.25 GBaud Enable"):
                            self.section_name = self.old_section
                            skip_outline = True

                        # Correct Rev 2.2 Part 6 Section 10.7.4.6 parsing
                        if (self.section_name == "10.0 Gb/s link"):
                            self.section_name = self.old_section
                            skip_outline = True

                        if self.create_outline and not skip_outline:
                            self.outline[self.part_name][self.chapter_name].append(self.section_name)
                        self.old_section = self.section_name
                    else:
                        logging.debug("Skipping sect: %s" % sect[0:100])

            # Only parse requirements for new sections...
            if not [self.part_name, self.chapter_name, self.section_name] in self.new_secs:
                continue
                
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
                new_reqt[self.REQTS[RequirementFields.REVISION]] = self.revision
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
            chapter_number_found = re.search(r"Chapter ([0-9]+) ", new_chapter_name)
            if chapter_number_found:
                self.chapter_number = chapter_number_found.group(1).strip()
                self.chapter_name = new_chapter_name.strip()
                self.chapter_name = re.sub("  +", " ", self.chapter_name)
                logging.info("chapter_name: '" + self.chapter_name + "'")
                logging.info("part_name: '" + self.part_name + "'")
                if self.create_outline and not self.part_name == '':
                   self.outline[self.part_name].update({self.chapter_name:[]})
            if self.chapter_number is None or self.part_name == "":
                logging.info("No chapter number/part name found yet, skipping " + chapter[0:50])
                continue
            self.section_number = self.chapter_number + "."
            self.section_prefix = r">" + self.chapter_number + r"."
            self.sections = chapter[end_idx:].split(self.section_prefix)
            logging.debug("Parse Sections: %s %s %d" % (self.section_number, self.section_prefix, len(self.sections)))
            self.parse_sections()
            if self.create_outline:
                if len(self.outline[self.part_name][self.chapter_name]) == 0:
                    del self.outline[self.part_name][self.chapter_name]

    def print_reqts(self):
        if self.create_outline:
            return
        if len(self.reqts) == 0:
            print "No requirements found for " + self.part_num
            return 0

        print "Revision, Part, Chapter, Section, Type, Sentence"
        for reqt in self.reqts:
            print ("'%s'" % "', '".join(reqt))

    def print_outline(self):
        if not self.create_outline:
            return
        if len(self.outline) == 0:
            print "No outline available"
            return 0

        print "Revision, Part, Chapter, Section"
        for part in self.outline:
            for chapter in self.outline[part]:
                for section in self.outline[part][chapter]:
                    print "'" + self.revision + "', '" +  part + "', '" + chapter + "', '" + section + "'"

    # Perform character substitutions to simplify parsing of text and correct
    # some text conversion errors...
    def _condition_all_text(self):
        # Remove carriage returns, newlines, and tabs.
        self.all_text = re.sub('\n', ' ', self.all_text)
        self.all_text = re.sub('\r', ' ', self.all_text)
        self.all_text = re.sub('\t', ' ', self.all_text)

        # Fix Rev 1.3 special characters
        self.all_text = re.sub("™", '', self.all_text)
        self.all_text = re.sub('•', '', self.all_text)
        self.all_text = re.sub("“", '"', self.all_text)
        self.all_text = re.sub("”", '"', self.all_text)
        self.all_text = re.sub("’", "'", self.all_text)

        # In Revision 3.2 and 4.0, superscripts were dropped.
        # Change this case to use a '^' <carat> character
        self.all_text = re.sub("2Mask", '2^Mask', self.all_text)

        # Fix Rev 1.3 text defects
        self.all_text = re.sub('LogicalSpecification', 'Logical Specification', self.all_text)
        self.all_text = re.sub('SpecificationPart', 'Specification Part', self.all_text)
        self.all_text = re.sub('PhysicalLayer', 'Physical Layer', self.all_text)
        self.all_text = re.sub('DeviceInter-operability', 'Device Inter-operability', self.all_text)
        self.all_text = re.sub('4.2.7 Type 3–4 Packet Formats \(Reserved\)',
                      '<P>4.2.7 Type 3–4 Packet Formats (Reserved) </P>', self.all_text)
        self.all_text = re.sub('4.2.8 Type 5 Packet Format \(Write Class\)',
                      '<P>4.2.8 Type 5 Packet Format (Write Class) </P>', self.all_text)
        self.all_text = re.sub('RapidIOTM', 'RapidIO', self.all_text)
        self.all_text = re.sub('TransportSpecification', 'Transport Specification', self.all_text)
        self.all_text = re.sub('SpecificationAnnex', 'Specification Annex', self.all_text)

        # Convert Rev 1.3 Part 5 title to match subsequent specifications
        self.all_text = re.sub("MemoryLogical", "Memory Logical", self.all_text)

        # Convert Rev 1.3 Part 9 title to match subsequent specifications
        self.all_text = re.sub("LayerExtensions", "Layer Extensions", self.all_text)

        # Convert Rev 1.3 terminology to industry standard
        self.all_text = re.sub("8B/10B", "8b/10b",  self.all_text)

        # Correct Rev 1.3 Part 6 Register description titles
        self.all_text = re.sub("CSRs\(Block", "CSRs (Block", self.all_text)

        # Correct Rev 1.3 Part 8 title
        self.all_text = re.sub("ManagementExtensions",
                               "Management Extensions", self.all_text)

        # Correct Rev 1.3 Part 11 Section 1.1/1.2 Overview
        self.all_text = re.sub("1.1 Overview",
                               "1.2 Overview", self.all_text)

        # Correct Rev 2.2 XML special characters...
        self.all_text = re.sub("&#8482;", "", self.all_text)
        self.all_text = re.sub("&#8211;", "–", self.all_text)
        self.all_text = re.sub("&#8226;", "", self.all_text)
        self.all_text = re.sub("&#8221;", '"', self.all_text)
        self.all_text = re.sub("&#8220;", '"', self.all_text)
        self.all_text = re.sub("&gt;", ">", self.all_text)
        self.all_text = re.sub("&lt;", "<", self.all_text)

        # Correct Rev 2.2 XML issues register table references,
        # Configuration Space Offset and Block Offset xml
        self.all_text = re.sub("&#61472;</P>", "", self.all_text)
        self.all_text = re.sub("&#61472;", "", self.all_text)
        self.all_text = re.sub("<P>\(Configuration Space Offset",
                               "(Configuration Space Offset", self.all_text)
        self.all_text = re.sub("<P>\(Block Offset",
                               " (Block Offset", self.all_text)
        self.all_text = re.sub("CSR\(Block Offset ",
                               "CSR (Block Offset ", self.all_text)
        self.all_text = re.sub("\<P\>\(Offset ",
                               " (Offset ", self.all_text)
        self.all_text = re.sub("Header\(Block Offset ",
                               "Header (Block Offset ", self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss the start of Part 4...
        self.all_text = re.sub("Interconnect Specification \</P\>",
                               "Interconnect Specification ", self.all_text)
        self.all_text = re.sub("\<P\>Part 4: Physical",
                               "Part 4: Physical", self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss-lable Part 5 Chapter 5 5.2.3.6 TLB Invalidate Entry,
        # TLB Invalidate Entry Synchronize Operations
        self.all_text = re.sub("Invalidate Entry Synchronize \</P\>",
                               "Invalidate Entry Synchronize ", self.all_text)
        self.all_text = re.sub("\<P\>Operations \</\P>",
                               "Operations </P>", self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss-lable Part 5 Chapter 5 6.7 Data Cache and Instruction Cache
        # Invalidate Operations
        #
        # Note: "Operations" fix in previous block is also necessary for
        #       this fix.
        self.all_text = re.sub("Instruction Cache Invalidate \</P\>",
                               "Instruction Cache Invalidate ", self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss-lable Part 5 Chapter 6 6.9 TLB Invalidate Entry,
        # TLB Invalidate Entry Synchronize Operations
        self.all_text = re.sub("Entry, TLB Invalidate Entry \</P\>",
                               "Entry, TLB Invalidate Entry ", self.all_text)
        self.all_text = re.sub("\<P\>Synchronize Operations \</P\>",
                               "Synchronize Operations </P>", self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss-lable Part 5 Chapter 7 7.6 Resolving an Outstanding
        # READ_TO_OWN_OWNER Transaction
        self.all_text = re.sub("Resolving an Outstanding \</P\>",
                               "Resolving an Outstanding ", self.all_text)
        self.all_text = re.sub("\<P\>READ_TO_OWN_OWNER Transaction \</P\>",
                               "READ_TO_OWN_OWNER Transaction </P>",
                                self.all_text)

        # Correct Rev 2.2. XML issue that would otherwise cause parser 
        # to mislable Part 6 Chapter 8 Section 8.5.11
        self.all_text = re.sub("Transmitter and </P>    <P>Receiver",
                               "Transmitter and Receiver",
                                self.all_text)

        # Correct Rev 2.2. XML issue that would otherwise cause parser 
        # to mislable Part 6 Chapter 8 Section 8.7.4.5
        self.all_text = re.sub("Cumulative Distribution </P>    <P>Function",
                               "Cumulative Distribution Function",
                                self.all_text)

        # Correct Rev 2.2. XML issue that would otherwise cause parser 
        # to mislable Part 6 Chapter 9 Section 9.3
        self.all_text = re.sub("I Transmitter and </P>    <P>Receiver Specifications",
                               "I Transmitter and Receiver Specifications",
                                self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss-lable Part 6 Chapter 9 1.25 Gbaud, 2.5Gbaud, and 3.125 Gbaud LP-Serial Links
        self.all_text = re.sub("1.25Gbaud, 2.5Gbaud, and \</P\>",
                               "1.25 Gbaud, 2.5 Gbaud, and ", self.all_text)
        self.all_text = re.sub("\<P\>3.125Gbaud LP-Serial Links \</P\>",
                               "3.125 Gbaud LP-Serial Links </P>",
                                self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss-lable Part 6 Chapter 10 5 Gbaud and 6.25 Gbaud LP-Serial
        self.all_text = re.sub("5Gbaud and 6.25Gbaud LP-Serial \</P\>",
                               "5 Gbaud and 6.25 Gbaud LP-Serial ", self.all_text)
        self.all_text = re.sub("\<P\>Links \</P\>",
                               "Links </P>",
                                self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss-lable Part 6 Section 10.1.5 
        self.all_text = re.sub("Transmitter and Receiver </P>    <P>Specifications",
                               "Transmitter and Receiver Specifications",
                               self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss-lable Part 7 Chapter 2 System Exploration and Initialization
        self.all_text = re.sub("Chapter 2 System Exploration and \</P\>",
                               "Chapter 2 System Exploration and ", self.all_text)
        self.all_text = re.sub("\<P\>Initialization",
                               "Initialization", self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss-lable Part 9 Chapter 2 Logical Layer Flow Control Operation
        self.all_text = re.sub("Logical Layer Flow Control \</P\>",
                               "Logical Layer Flow Control ", self.all_text)
        self.all_text = re.sub("\<P\>Operation \</\P>",
                               "Operation </P>", self.all_text)

        # Correct Rev 2.2 XML issue that would otherwise cause parser
        # to miss-lable Part 9 Chapter 4 Logical Layer Flow Control
        # Extensions Register Bits
        self.all_text = re.sub("Logical Layer Flow Control \</P\>",
                               "Logical Layer Flow Control ", self.all_text)
        self.all_text = re.sub("\<P\>Extensions Register Bits \</\P>",
                               "Extensions Register Bits </P>", self.all_text)

        # Correct Rev 3.2 Part 3 Section 3.7.3 title
        self.all_text = re.sub("Routing Table Entry </H3>    <P>CSR \(Offset",
                               "Routing Table Entry CSR (Offset",
                               self.all_text)

        # Correct Rev 3.2 Part 6 Section 3.5.5.3 title
        self.all_text = re.sub("Port-status1 Command",
                               "Port-status Command",
                               self.all_text)

        # Correct Rev 3.2 Part 6 Chapter 9 title
        self.all_text = re.sub("Specificationsfor", "Specifications for", self.all_text)

        # Correct Rev 2.2 Part 6 Chapter 10 title
        # Correct Rev 3.2 Part 6 Chapter 10 title
        # Correct Rev 4.0 Part 6 Chapter 10 title
        self.all_text = re.sub("Chapter 10  1.25 Gbaud, 2.5 Gbaud, and </P>    <P>3.125 Gbaud LP-Serial Links",
                               "Chapter 10 1.25 Gbaud, 2.5 Gbaud, and 3.125 Gbaud LP-Serial Links", self.all_text)

        # Correct Rev 2.2 Part 6 Chapter 11.4.1.1 title
        # Correct Rev 3.2 Part 6 Chapter 11.4.1.1 title
        # Correct Rev 4.0 Part 6 Chapter 11.4.1.1 title
        self.all_text = re.sub("Test Patterns1", "Test Patterns", self.all_text)

        # Correct Rev 2.2 Part 6 Chapter 11.7.1.2.2 title
        # Correct Rev 3.2 Part 6 Chapter 11.7.1.2.2 title
        # Correct Rev 4.0 Part 6 Chapter 11.7.1.2.2 title
        self.all_text = re.sub("Band Limited1", "Band Limited", self.all_text)

        # Correct Rev 2.2 Part 8 Section 1.2.4 title
        self.all_text = re.sub("Rate Failed Threshold is </P>    <P>Reached",
                               "Rate Failed Threshold is Reached",
                                self.all_text)

        # Correct Rev 2.2 Part 8 Section 1.2.4 title
        self.all_text = re.sub("Enable and Capture </P>    <P>CSRs",
                               "Enable and Capture CSRs",
                                self.all_text)

        # Correct Rev 3.2 Part 7 Chapter 2 title
        self.all_text = re.sub("andInitialization",
                               "and Initialization", self.all_text)
        self.all_text = re.sub('3.0, 10/2013 © Copyright RapidIO.org ', '', self.all_text)
        self.all_text = re.sub('[0-9+] RapidIO.org', '', self.all_text)
        self.all_text = re.sub('RapidIO.org [0-9+]', '', self.all_text)
        self.all_text = re.sub(r" id=\"LinkTarget_[0-9]*\">", r'>',  self.all_text)

        # Correct Rev 3.2 Part 8 Section 2.5.9 title
        self.all_text = re.sub("Destination ID Capture </P>    <P>CSR   (Block Offset 0x20)",
                               "Destination ID Capture CSR (Block Offset 0x20)",
                               self.all_text)

        # Correct Rev 3.2 Part 9 Section 3.4.5 title
        self.all_text = re.sub("Rules for Traffic Management Supported",
                               "Rules for Traffic Management </P> Supported",
                               self.all_text)

        # Correct Rev 3.2 & 4.0 Part 11 Section 3.4.7 title
        self.all_text = re.sub("Mask x Clear Register y CSR </P>     \(Offset",
                               "Mask x Clear Register y CSR (Offset",
                               self.all_text)

    # Work around embedded specification part references in
    # Version 4.0, Part 10 Chapter 5
    def _fixup_parts(self):
        new_parts = []
        for i, part in enumerate(self.parts):
            logging.info("Part %d:'%s'" % (i, part[0:50]))
            chapter_number_found = re.search(r"Chapter ([0-9]*) ", part)
            if chapter_number_found:
                logging.info("    Added")
                new_parts.append(part)
            else:
                if len(new_parts) > 0:
                   new_parts[-1] += part
                   logging.info("    Appended to part %d:'%s'"
                                      % (i-1, new_parts[-1][0:50]))
                else:
                   logging.info("    Dropped.")
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
            logging.info("target_number " + self.target_number)
            logging.info("target_is_annex " + self.target_is_annex)

        spec_file = open(self.input_xml)
        self.all_text = spec_file.read()
        spec_file.close()

        self.all_text = " " + self.all_text + "  "
        self._condition_all_text()
        output_xml = self.input_xml + ".output"

        output = open(output_xml, "w")
        output.write(self.all_text)
        output.close()

        self.parts = self.all_text.split( ">" + part_header)
        self._fixup_parts()
        self.part_name = ''
        self.part_number = ''
        self.part_annex = False
        for part in self.parts:
            part = part_header + part
            new_part_name = part[:part.find('<')].strip()
            # Jiggery pokery below is required to weed out references to
            # specification parts found within other parts of the specification.
            # This is dependent on all of these references always being backward
            # i.e. Part 10   can  refer to Part 1, but
            #      Part  1 cannot refer to Part 10
            # This dependency is true up to Revision 4.0.
            found_number = re.search(" ([0-9]*):", new_part_name)
            if found_number:
                new_part_number = int(found_number.group(1))
                new_part_annex = new_part_name.find("Annex") >= 0
                # Always skip Part 4, Parallel RapidIO
                if new_part_number == 4 and not new_part_annex:
                    logging.info("Skipping part 4: %s" % part[0:50])
                    continue
                # Always skip Annex 1 and 2
                if new_part_number < 3 and new_part_annex:
                    continue
                if (self.part_name == ''
                    or (new_part_annex and not self.part_annex)
                    or (not (new_part_annex ^ self.part_annex)
                        and (new_part_number > self.part_number))):
                    new_part_name = re.sub("  +", " ", new_part_name)
                    self.part_name = new_part_name
                    self.part_number = new_part_number
                    self.part_annex = new_part_annex
                    logging.info("part_name: " + self.part_name +
                                  " number " + str(self.part_number) +
                                  " annex " + str(self.part_annex))
                    if self.create_outline:
                       self.outline.update({self.part_name:OrderedDict()})

            if self.target_number is not None:
                if self.part_number is None or self.part_number == '':
                    continue
                sys.stdout.flush()
                if ((not int(self.part_number) == int(self.target_number))
                    or not (self.target_is_annex == self.part_annex)):
                    del self.outline[self.part_name]
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
    parser.add_option('-o', '--outline',
            dest = 'create_outline',
            action = 'store_true', default=False,
            help = 'Create an outline of the standard.',
            metavar = 'OUTLINE')
    parser.add_option('-r', '--revision',
            dest = 'override_revision',
            action = 'store', type = 'string', default=None,
            help = 'Override the specification revision for debug purposes.',
            metavar = 'REVISON')
    parser.add_option('-n', '--new_secs',
            dest = 'new_secs_filepath',
            action = 'store', type = 'string',
            help = 'File listing new sections in this specification revision.',
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

    if options.new_secs_filepath is not None:
        if not os.path.isfile(options.new_secs_filepath):
            print "New sections File '" + options.new_secs_filepath +"' does not exist."
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

    std_parser = RapidIOStandardParser(options.create_outline,
                                       options.filename_of_standard,
                                       options.target_part,
                                       options.override_revision,
                                       options.new_secs_filepath)
    std_parser.parse_parts()
    std_parser.print_reqts()
    std_parser.print_outline()

if __name__ == '__main__':
    sys.exit(main())
