# -*- coding: utf-8 -*-

"""
USAGE: %(program)s WIKI_XML_DUMP CONFIG_FILE

Get claims from a Wikipedia dump that are marked as "[CITATION NEEDED]"
and return probable online sources supporting these claims. The input is a
bz2-compressed dump of Wikipedia articles, in XML format.

This creates a single file:

* `report.html`: an HTML report containing claims and their respective probable
supporting sources

WIKI_XML_DUMP is the exported dump of articles of your choice to process
automatically, must be bz2-compressed

CONFIG_FILE should first be created by running createwikidict.py and then
updated with appropriate information (see README for more information)

Example: python runfinder.py ~/path/to/chosen/articles.xml.bz2 ~/path/to/_wikifinder.cfg
"""
# Standard imports
import ConfigParser
import logging
import os.path
import sys

# Third-party imports
from gensim.corpora.dictionary import Dictionary
from finderwikicorpus import FinderWikiCorpus
from bingapi import BingResponse

# Application-specific imports
import report_generator
from codecs import ignore_errors


# Module functions
def _get_response_data(article_claims, config_file):
    """
    Searches for candidate source pages for the given articles and claims.
    
    Args:
        article_claims: A list of ArticleClaims objects for the articles
            searched.
        config_file: The path to the application configuration file.
        
    Returns:
        A list of ArticleResponse objects to be rendered in the final HTML
        report.
    """
    result = []
    for article in article_claims:
        config = ConfigParser.ConfigParser()
        
        # read the configuration file again in case the [skipsites] section has
        # been updated
        config.read(config_file)
        
        try:
            skipsites = [key for (key, value)
                         in config.items('skipsites')
                         if value == 'true']
        except:
            pass
        
        claims_responses = []
        
        for claim in article.claims:
            #try:
            response = BingResponse(claim.article_text, claim.text,
                                    claim.query, skipsites, config_file,
                                    api_key)
            #except SystemExit:
            #    print 'Error: your Bing API key does not appear to be valid'
            #    sys.exit(1)
            #except:
            #    pass
            
            try:
                claim_responses = ClaimResponses(claim.text,
                                                 response.google_link,
                                                 response.valid_sites)
                claims_responses.append(claim_responses)
            except:
                pass
            
            
        
        article_response = ArticleResponse(article.id, article.title,
                                      claims_responses)
        result.append(article_response)
        
    return result


# Module classes
class ClaimResponses(object):
    """
    A wrapper for the rendering of final reports.
    
    Wraps information relevant to a single claim of a particular article.
    
    Attributes:
        claim_text: The text of the claim.
        claim_id: The ID used for rendering purposes. Has the format of
            'article_id-claim_number'.
        google_link: A link to easily access Google results for the computed
            query.
        valid_sites: A list of tuples of the format (url, page_name,
            bing_search_page_snippet, similar_paragraph_found).
    """
    
    def __init__(self, claim_text, google_link, found_response_tuples):
        """
        Initializes an instance of a ClaimResponses object.
        
        Args:
            claim_text: Text of the claim.
            google_link: A link to easily access Google results for the
                computed query.
            found_response_tuples: A list of tuples of the format (url,
                page_name, bing_search_page_snippet, similar_paragraph_found),
                wrapping the found candidate pages for a source.
        """
        self.claim_text = claim_text
        self.claim_id = '-' 
        self.google_link = google_link
        self.valid_sites = [response_tuple
                            for response_tuple
                            in found_response_tuples]
            

class ArticleResponse(object):
    """
    A wrapper for the rendering of final reports.
    
    Wraps information relevant to a particular article.
    
    Attributes:
        article_id: The original Wikipedia ID of the article.
        article_title: The title of the article.
        claims_responses: A list of ClaimResponses objects for all
            unsubstantiated claims found in the article.
    """
    
    def __init__(self, article_id, article_title, claims_responses):
        """
        Initializes an instance of an ArticleResponse object.
        
        Args:
            article_id: The original Wikipedia ID of the article.
            article_title: The title of the article.
            claims_responses: A list of ClaimResponses objects for all
                unsubstantiated claims found in the article.
        """
        self.article_id = article_id
        self.article_title = article_title
        self.claims = [response for response in claims_responses]
        
        i = 0
        for claim in self.claims:
            claim.claim_id = article_id + '-' + str(i)
            i += 1
    

# Main function
if __name__ == '__main__':
    """
    The entry point for the application.
    
    Runs the whole process of searching for unsubstantiated claims and
    candidate source pages. Generates an HTML report for its findings.
    """
    program = os.path.basename(sys.argv[0])
    logger = logging.getLogger(program)
    
    logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s')
    
    logging.root.setLevel(level=logging.INFO)
    logger.info("running %s" % ' '.join(sys.argv))
    
    # check the validity of the input
    if len(sys.argv) < 3:
        print(globals()['__doc__'] % locals())
        sys.exit(1)
    
    inp, config_file = sys.argv[1:3]
    
    if not (os.path.isfile(os.path.abspath(config_file))
            and os.path.isfile(os.path.abspath(inp))):
        
        print(globals()['__doc__'] % locals())
        sys.exit(1)
        
    logger.info('loading configuration information')
    
    config = ConfigParser.ConfigParser()
    config.read(config_file)
    
    article_count = config.getint('general', 'articlecount')
    wordids = config.get('general', 'wordids_path')
    
    try:
        api_key = config.get('general', 'bing_api_key')
    except ConfigParser.NoOptionError:
        print("The configuration file needs to contain a 'bing_api_key' option"
              " specifying the API key to be used when searching for sources")
        sys.exit(1)
        
    if api_key == 'none':
        print("The configuration file needs to contain a valid 'bing_api_key'"
              " in order for the tool to work properly")
        sys.exit(1)
        
    
    try:
        set_citation = {unicode(key.lower(), 'utf-8')
                        for (key, value)
                        in config.items('citation-needed')
                        if value == 'true'}
    except ConfigParser.NoSectionError:
        print("The configuration file needs to contain a [citation-needed]"
              " section with template names to be taken into account"
              " identifying a 'Citation needed' template")
        sys.exit(1)
        
    try:
        quote_identifier = config.get('quote', 'quote').lower()
        text_identifier = config.get('quote', 'text').lower()
        quote_identifiers = (quote_identifier, text_identifier)
    except (ConfigParser.NoSectionError, ConfigParser.NoOptionError):
        print("The configuration file needs to contain a [quote]"
              " section with 'quote' and 'text' options with the"
              " keywords in a Quote template")
        sys.exit(1)
    
    logger.info('finished loading configuration information')
    logger.info('loading dictionary mappings, this can take up to several'
                ' minutes')
    
    
    dictionary = Dictionary.load_from_text(wordids)
    
    logger.info('done loading dictionary mappings')
    logger.info('searching for unsubstantiated claims')
    
    finderWiki = FinderWikiCorpus(inp, dictionary, article_count, set_citation,
                                  quote_identifiers)
    article_claims = finderWiki.get_claims()
    base_url = finderWiki.base_url
    
    logger.info('done searching for unsubstantiated claims')
    
    
    logger.info('searching for probable sources, this can take a while')        
    result = _get_response_data(article_claims, config_file)
    logger.info('done searching for probable sources')
    
    logger.info('generating HTML report')
    report_generator.create_report(result, base_url)
    logger.info("saved output into report.html")
