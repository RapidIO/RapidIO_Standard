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

REVISION = "Revision"
PART = "Part"
CHAPTER = "Chapter"
SECTION = "Section"
TYPE = "TYPE"
SENTENCE = "Sentence"

REQTS = {REVISION:0,
         PART:1,
         CHAPTER:2,
         SECTION:3,
         TYPE:4,
         SENTENCE:5}

TYPE_RECOMMENDATION = "Recommendation"
TYPE_REQUIREMENT = "REQUIREMENT"

def print_reqts(reqts):
    print "Revision, Part, Chapter, Section, Type, Sentence"
    for reqt in reqts:
        print reqt

def create_parser():
    parser = OptionParser()
    parser.add_option('-f', '--file',
            dest = 'filename_of_standard',
            action = 'store', type = 'string',
            help = 'RapidIO Specification Stack in XML format.',
            metavar = 'FILE')
    parser.add_option('-p', '--part',
            dest = 'part_name',
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

    if options.part_name is None:
        options.part_name = '*'
    return options

caps = "([A-Z])"
prefixes = "(Mr|St|Mrs|Ms|Dr)[.]"
suffixes = "(Inc|Ltd|Jr|Sr|Co)"
starters = "(Mr|Mrs|Ms|Dr|He\s|She\s|It\s|They\s|Their\s|Our\s|We\s|But\s|However\s|That\s|This\s|Wherever)"
acronyms = "([A-Z][.][A-Z][.](?:[A-Z][.])?)"
websites = "[.](com|net|org|io|gov)"
digits = "([0-9])" 

def split_into_sentences(text):
    text = re.sub(prefixes,"\\1<prd>",text)
    text = re.sub(r"\.\.+",r"<ellipsis>",text)
    text = re.sub(websites,"<prd>\\1",text)
    text = re.sub(digits + "[.]" + digits,"\\1<prd>\\2",text)
    if "Ph.D" in text: text = text.replace("Ph.D.","Ph<prd>D<prd>")
    text = re.sub("\s" + caps + "[.] "," \\1<prd> ",text)
    text = re.sub(acronyms+" "+starters,"\\1<stop> \\2",text)
    text = re.sub(caps + "[.]" + caps + "[.]" + caps + "[.]","\\1<prd>\\2<prd>\\3<prd>",text)
    text = re.sub(caps + "[.]" + caps + "[.]","\\1<prd>\\2<prd>",text)
    text = re.sub(" "+suffixes+"[.] "+starters," \\1<stop> \\2",text)
    text = re.sub(" "+suffixes+"[.]"," \\1<prd>",text)
    text = re.sub(" " + caps + "[.]"," \\1<prd>",text)
    if '"' in text: text = text.replace('"',"<quote>")
    if "!" in text: text = text.replace("!\"","\"!")
    if "?" in text: text = text.replace("?\"","\"?")
    text = text.replace(".",".<stop>")
    text = text.replace("?","?<stop>")
    text = text.replace("!","!<stop>")
    text = text.replace("<prd>",".")
    sentences = text.split("<stop>")
    sentences = sentences[:-1]
    sentences = [s.strip() for s in sentences]
    return sentences

# Sneaky: Remove XML but replace tags with periods.
# This may result in many empty sentences, but it also results
# in ignoring a lot of figure/table titles, headers, etc...
def remove_xml(text):
    return re.sub(r'\<[^>]+\>', " . ", text)

def parse_sections(sections, part_name, chapter_name, section_number):
    REQT_KW = ["must", "shall"]
    REC_KW = ["should", "recommend"]
    SECTION_END = "</"

    reqts = []
    for sect in sections:
        if sect[0] < '0' or sect[0] > '9':
            continue
        sect = section_number + sect
        heading_end = sect.find(SECTION_END)
        section_name = sect[:heading_end].strip()
        print "section_name :" + section_name
        sect = remove_xml(sect)
        sentences = split_into_sentences(sect[heading_end + len(SECTION_END):])
        for s in sentences:
            s_type = None
            if any(sub in s for sub in REQT_KW):
                s_type = TYPE_REQUIREMENT;
            elif any(sub in s for sub in REC_KW):
                s_type = TYPE_RECOMMENDATION;
            if s_type is None:
                continue
            new_reqt = [None] * (max(REQTS.values()) + 1)
            new_reqt[REQTS[REVISION]] = "4.0"
            new_reqt[REQTS[PART]] = part_name
            new_reqt[REQTS[CHAPTER]] = chapter_name
            new_reqt[REQTS[SECTION]] = section_name
            new_reqt[REQTS[TYPE]] = s_type
            new_reqt[REQTS[SENTENCE]] = s
            reqts.append(new_reqt)
    return reqts

def parse_chapters(heading_1s, part_name):
    h1_start = ">"
    h1_end = r"</H1>"

    reqts = []
    for h1 in heading_1s:
        start_idx = h1.find(h1_start) + len(h1_start)
        end_idx = start_idx + h1[start_idx:].find(h1_end) + len(h1_end)
        chapter_name = h1[start_idx:end_idx].strip()
        if chapter_name.find("Chapter") < 0:
            continue
        print "chapter_name: '" + chapter_name + "'"
        chapter_number_found = re.search("Chapter ([0-9]*)", chapter_name)
        if not chapter_number_found:
            print "Skipping chapter, no number found..."
            continue
        chapter_number = chapter_number_found.group(1)
        section_number = chapter_number + "."
        section_prefix = r">" + chapter_number + r"."
        sections = h1[end_idx:].split(section_prefix)
        reqts += parse_sections(sections, part_name, chapter_name, section_number)
    return reqts

# Perform character substitutions to simplify parsing of text and correct
# some text conversion errors...
def condition_text(text):
    text = re.sub('\n', ' ', text)
    text = re.sub('\t', '', text)
    text = re.sub('\r', ' ', text)
    text = re.sub('™', '', text)
    text = re.sub('•', '', text)
    text = re.sub("“", '"', text)
    text = re.sub("”", '"', text)
    text = re.sub('LogicalSpecification', 'Logical Specification', text)
    text = re.sub('SpecificationPart', 'Specification Part', text)
    text = re.sub('PhysicalLayer', 'Physical Layer', text)
    text = re.sub('DeviceInter-operability', 'Device Inter-operability', text)
    text = re.sub('RapidIOTM', 'RapidIO', text)
    text = re.sub('3.0, 10/2013 © Copyright RapidIO.org ', '', text)
    text = re.sub(r" id=\"LinkTarget_[0-9]*\">", r'>',  text)
    return text

def parse_parts(spec_file_name, target_part):
    part_header = "RapidIO Interconnect Specification "
    annex = "Annex"
    reqts = []
    
    target_number = None
    target_is_annex = None

    found_number = re.search(" ([0-9]*)", target_part)
    if found_number:
        target_number = int(found_number.group(1))
        target_is_annex = target_part.find(annex) >= 0
        print "target_number ", target_number
        print "target_is_annex ", target_is_annex
    
    spec_file = open(spec_file_name)
    all_text = spec_file.read()
    spec_file.close()

    all_text = " " + all_text + "  "
    all_text = condition_text(all_text)
    parts = all_text.split( ">" + part_header)
    part_name = ''
    part_number = ''
    part_annex = False
    for part in parts:
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
            if (part_name == ''
                or (new_part_annex and not part_annex)
                or (not (new_part_annex ^ part_annex) 
                    and (new_part_number > part_number))):
                part_name = new_part_name
                part_number = new_part_number
                part_annex = new_part_annex
        print "part_name: " + part_name
        
        if not target_number is None:
            if ((not part_number == target_number)
                or not (target_is_annex == part_annex)):
                continue
        heading_1s = part[len(new_part_name):].split('<H1')
        reqts += parse_chapters(heading_1s, part_name)
    return reqts

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

    reqts = parse_parts(options.filename_of_standard, options.part_name)
    
    if len(reqts) == 0:
        print "No requirements found for Part " + options.part_name
        return 0

    print_reqts(reqts)

if __name__ == '__main__':
    sys.exit(main())
