#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Radim Rehurek <radimrehurek@seznam.cz>
# Copyright (C) 2012 Lars Buitinck <larsmans@gmail.com>
# Copyright (C) 2017 Vojtech Krajnansky <vojtech.krajnansky@gmail.com>
# Licensed under the GNU LGPL v2.1 - http://www.gnu.org/licenses/lgpl.html


import bz2
import multiprocessing
import re
from xml.etree.cElementTree import iterparse

from gensim import utils
from gensim.corpora.wikicorpus import *
from claims import ArticleClaims


# Module functions
def is_cn(template, set_citation):
    """
    Determines if a Wiki template is a [Citation needed] template.
    
    Args:
        template: The Wiki template.
        set_citation: A set of [Citation needed] template identifiers to use.
        
    Returns:
        True if a template is deemed to be a [Citation needed] template, False
        otherwise.
    """
    text = (template.lower().split("|")[0]
            .replace("{", "").replace("}", "").strip())
    
    if text in set_citation:
        return True
    return False


def is_quote(template, identifier):
    """
    Determines if a Wiki template is a [Quote] template.
    
    Args:
        template: The Wiki template.
        set_citation: A [Quote] template identifier to use.
        
    Returns:
        True if a template is deemed to be a [Quote] template, False
        otherwise.
    """
    text = (template.lower().split("|")[0]
            .replace("{", "").replace("}", "").strip())
    if text == identifier:
        return True
    return False


def get_quote(template, text_identifier):
    """
    Attempts to retrieve the text portion of the [Quote] template.
    
    If no text attribute is found, retrieves the whole of the template after
    the Quote identifier. This means that some metadata may get included in the
    returned result.
    
    Args:
        template: The template to be parsed.
        text_identifier: The identifier of the text parameter.
        
    Returns:
        The text portion of the claim. If no text attribute is found in the
        claim returns everything that follows the first attribute (the [Quote]
        identifier).
    """
    split = template.lower().split("|")

    quote = ''
    for part in split:
        identifier_with_euqals = text_identifier + '='
        if identifier_with_euqals in part:
            quote = part.split(identifier_with_euqals)[1].strip()
    
    if quote == '':
        try:
            quote = "".join(split[1:]).replace("}", "").strip()
        except:
            pass
    return quote
    
def replace_citation_templates(s, set_citation, quote_identifier,
                               text_identifier):
    """
    Remove template wikimedia markup and replace "Citation needed" templates
    with $$CNMARK$$.
    
    Return a copy of `s` with all the wikimedia markup template removed. See
    http://meta.wikimedia.org/wiki/Help:Template for wikimedia templates
    details.
    
    Try to preserve most of the quote text from Quote templates.
    
    Note: Since template can be nested, it is difficult remove them using
    regular expresssions.
    """

    # Find the start and end position of each template by finding the opening
    # '{{' and closing '}}'
    n_open, n_close = 0, 0
    starts, ends = [], []
    in_template = False
    prev_c = None
    for i, c in enumerate(iter(s)):
        if not in_template:
            if c == '{' and c == prev_c:
                starts.append(i - 1)
                in_template = True
                n_open = 1
        if in_template:
            if c == '{':
                n_open += 1
            elif c == '}':
                n_close += 1
            if n_open == n_close:
                ends.append(i)
                in_template = False
                n_open, n_close = 0, 0
        prev_c = c

    # Remove all the templates and replace "Citation needed" templates with
    # $$CNMARK$$ and try to preserve quote template information
    aList = []
    for i, template in enumerate([s[start:end+1]
                                  for start, end
                                  in zip(starts, ends)]):
        aList.append([s[end + 1:start]
                      for start, end
                      in zip(starts + [None], [-1] + ends)][i])
        
        if is_cn(template, set_citation):			
            aList.append("$$CNMARK$$")
        elif is_quote(template, quote_identifier):
            pattern = re.compile("\n+")
            while (len(aList) != 0 and
                   re.match(pattern, aList[len(aList) - 1])):
                del aList[-1]
                
            aList.append('\n')
            aList.append(get_quote(template, text_identifier))

    if not aList:
        return ''.join([s[end + 1:start]
                        for start, end in zip(starts + [None], [-1] + ends)])

    aList.append([s[end + 1:start]
                  for start, end
                  in zip(starts + [None], [-1] + ends)][-1])
    return ''.join(aList)

def get_plain_with_cnmarks(text, set_citation, quote_identifiers):
    """
    Parse a Wikipedia dump article, returning its plaintext contents
    with a $$CNMARK$$ marker in place of {Citation needed} templates
    """
    text = re.sub(RE_P2, "", text)  # remove the last list (=languages)
    # the wiki markup is recursive (markup inside markup etc)
    # instead of writing a recursive grammar, here we deal with that by removing
    # markup in a loop, starting with inner-most expressions and working outwards,
    # for as long as something changes.
    text = replace_citation_templates(text, set_citation,
                                      quote_identifiers[0],
                                      quote_identifiers[1])
    text = remove_file(text)
    iters = 0
    while True:
        old, iters = text, iters + 1
        text = re.sub(RE_P0, "", text)  # remove comments
        text = re.sub(RE_P1, '', text)  # remove footnotes
        text = re.sub(RE_P9, "", text)  # remove outside links
        text = re.sub(RE_P10, "", text)  # remove math content
        text = re.sub(RE_P11, "", text)  # remove all remaining tags
        text = re.sub(RE_P14, '', text)  # remove categories
        text = re.sub(RE_P5, '\\3', text)  # remove urls, keep description
        text = re.sub(RE_P6, '\\2', text)  # simplify links, keep description only
        # remove table markup
        text = text.replace('||', '\n|')  # each table cell on a separate line
        text = re.sub(RE_P12, '\n', text)  # remove formatting lines
        text = re.sub(RE_P13, '\n\\3', text)  # leave only cell content
        # remove empty mark-up
        text = text.replace('[]', '')
        if old == text or iters > 2:  # stop if nothing changed between two iterations or after a fixed number of iterations
            break

    # the following is needed to make the tokenizer see '[[socialist]]s' as a single word 'socialists'
    text = text.replace('[', '').replace(']', '')  # promote all remaining markup to plain text
    return text

def get_article_claims(args):
    text, lemmatize, title,  pageid, set_citation, quote_identifiers = args
    text = utils.to_unicode(text, 'utf8', errors='ignore')
    text = utils.decode_htmlentities(text)
    plaintext = get_plain_with_cnmarks(text, set_citation, quote_identifiers)
    
    claims = ArticleClaims(pageid, title, plaintext)
    claims.from_text()
    
    return claims

class FinderWikiCorpus(WikiCorpus):
    """
    Parses Wiki dump articles into plaintext, retrieves unsubstituted claims.
    """
    def __init__(self, fname, dictionary, article_count, set_citation,
                 quote_identifiers, processes=None,
                 lemmatize=utils.has_pattern(), filter_namespaces=('0',)):
        WikiCorpus.__init__(self, fname, processes, False, dictionary,
                            filter_namespaces)
        
        self.set_citation = set_citation
        self.articlecount = article_count
        self.quote_identifiers = quote_identifiers
            
        self.base_url = self._get_base_wikipedia_url(bz2.BZ2File(self.fname),
                                                    filter_namespaces)
            
    def get_claims(self):
        """
        Iterate over the dump, creating a pseudo-XML file called "output" containing claims that are marked
        with the "citation needed" template
        """
        articles, articles_all = 0, 0
        positions, positions_all = 0, 0
        texts = ((text, self.lemmatize, title, pageid, self.set_citation, self.quote_identifiers) for title, text, pageid in extract_pages(bz2.BZ2File(self.fname), self.filter_namespaces))
        pool = multiprocessing.Pool(self.processes)
        # process the corpus in smaller chunks of docs, because multiprocessing.Pool
        # is dumb and would load the entire input into RAM at once...
        claim_list = []
        for group in utils.chunkize(texts, chunksize=10 * self.processes, maxsize=1):
            for claims in pool.imap(get_article_claims, group):  # chunksize=10):
                claim_list.append(claims)
        pool.terminate()

        #with open("output.finder", "w") as outfile:
        #    for claim in retList:
        #        outfile.write(claim)
        for x in claim_list:
            for c in x.claims:
                c.get_query(self.dictionary, self.articlecount)
            
        return claim_list
              
    @staticmethod      
    def _get_base_wikipedia_url(f, filter_namespaces=False):
        """
        Extract pages from a MediaWiki database dump = open file-like object `f`.
    
        Return an iterable over (str, str, str) which generates (title, content, pageid) triplets.
    
        """
        elems = (elem for _, elem in iterparse(f, events=("end",)))
    
        # We can't rely on the namespace for database dumps, since it's changed
        # it every time a small modification to the format is made. So, determine
        # those from the first element we find, which will be part of the metadata,
        # and construct element paths.
        elem = next(elems)
        namespace = get_namespace(elem.tag)
        ns_mapping = {"ns": namespace}
        siteinfo_tag = "{%(ns)s}siteinfo" % ns_mapping
        base_url_path = "./{%(ns)s}base" % ns_mapping
        pattern = re.compile(r"^https?:\/\/[[\w]*\.?]?wikipedia\.org")
        for elem in elems:
            if elem.tag == siteinfo_tag:
                return pattern.findall(elem.find(base_url_path).text)[0]
