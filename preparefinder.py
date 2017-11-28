#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 Radim Rehurek <radimrehurek@seznam.cz>
# Copyright (C) 2012 Lars Buitinck <larsmans@gmail.com>
# Modified 2017 by Vojtech Krajnansky <vojtech.krajnansky@gmail.com>
# Licensed under the GNU LGPL v2.1 - http://www.gnu.org/licenses/lgpl.html

"""
USAGE: %(program)s WIKI_XML_DUMP OUTPUT_PREFIX

Creates a dictionary of token-document frequency mapping. The input is a
bz2-compressed dump of Wikipedia articles, in XML format.

* WIKI_XML_DUMP: a bzip2-compressed dump of Wikipedia articles
* OUTPUT_PREFIX: the path prefix for the files to be created

This actually creates two files:

* `OUTPUT_PREFIX_wordids.txt`: mapping between words and their integer ids
* `OUTPUT_PREFIX_wikifinder.cfg`: a configuration file for the subsequent run
of runfinder.py

Example: python makecorpus.py ~/path/to/enwiki-latest-pages-articles.xml.bz2 ~/path/to/wiki_en/
"""

import logging
import os.path
import sys
import ConfigParser

from gensim.corpora import Dictionary, WikiCorpus


if __name__ == '__main__':
    program = os.path.basename(sys.argv[0])
    logger = logging.getLogger(program)

    logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s')
    logging.root.setLevel(level=logging.INFO)
    logger.info("running %s" % ' '.join(sys.argv))

    Config = ConfigParser.ConfigParser()
    
    # check and process input arguments
    if len(sys.argv) < 3:
        print(globals()['__doc__'] % locals())
        sys.exit(1)
    inp, outp = sys.argv[1:3]

    if not os.path.isdir(os.path.dirname(outp)):
        raise SystemExit("Error: The output directory does not exist. Create"
                         "the directory and try again.")

    # create the dictionary containing document frequencies for each token
    wiki = WikiCorpus(inp, lemmatize=False, dictionary=Dictionary())
    wiki.dictionary = Dictionary(wiki.get_texts(), prune_at = None)
    wiki.dictionary.save_as_text(outp + '_wordids.txt.bz2')
    
    # create the configuration file with default values
    config_file = open(outp + '_wikifinder.cfg', 'w')
    Config.add_section('general')
    Config.set('general', 'articlecount', wiki.length)
    Config.set('general', 'wordids_path', outp + '_wordids.txt.bz2')
    Config.set('general', 'bing_api_key', 'none')
    Config.add_section('citation-needed')
    Config.set('citation-needed', 'Citation needed', 'true')
    Config.set('citation-needed', 'Cn', 'true')
    Config.set('citation-needed', 'Fact', 'true')
    Config.set('citation-needed', 'Cb', 'true')
    Config.set('citation-needed', 'Ctn', 'true')
    Config.set('citation-needed', 'Ref?', 'true')
    Config.add_section('quote')
    Config.set('quote', 'quote', 'Quote')
    Config.set('quote', 'text', 'text')
    Config.add_section('skipsites')
    Config.set('skipsites', 'wikipedia.org', 'true')
    Config.set('skipsites', 'google.com', 'false')
    Config.set('skipsites', 'revolvy.com', 'true')
    Config.set('skipsites', 'wow.com', 'true')
    Config.set('skipsites', 'wikivisually.com', 'true')
    Config.set('skipsites', 'digplanet.com', 'true')
    Config.set('skipsites', 'everipedia.com', 'true')
    Config.set('skipsites', 'wikia.com', 'true')
    Config.set('skipsites', 'explained.today', 'true')
    Config.set('skipsites', 'wordpress.com', 'true')
    Config.set('skipsites', 'infogalactic.com', 'true')
    Config.set('skipsites', 'wikiomni.com', 'true')
    Config.set('skipsites', 'jsonpedia.org', 'true')
    Config.set('skipsites', 'what-is-this.net', 'true')
    Config.set('skipsites', 'sensagent.com', 'true')
    Config.set('skipsites', 'my-definitions.com', 'true')
    Config.set('skipsites', 'thefullwiki.org', 'true')
    Config.set('skipsites', 'pediaview.com', 'true')
    
    Config.write(config_file)
    config_file.close()
    
    logger.info("finished running %s" % program)
    