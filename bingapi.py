# -*- coding: utf-8 -*-

# Standard imports
import urllib2

# Third-party imports
import justext
import gensim
import requests


# Module functions
def _extract_hostname(url):
    """
    Extracts the hostname from a given URL.
    
    Args:
        url: The URL from which to retrieve only the hostname.
        
    Returns:
        The hostname of the given URL.
    """
    if (url.index("://") > -1):
        hostname = url.split('/')[2]
    else:
        hostname = url.split('/')[0]

    hostname = hostname.split(':')[0].split('?')[0]

    return hostname;


def _extract_root_domain(url):
    """
    Extracts only the root domain from a given URL.
    
    Args:
        url: The URL from which to retrieve only the root domain.
        
    Returns:
        The root domain of the given URL.
    """
    domain = _extract_hostname(url)
    split = domain.split('.')
    arr_length = len(split)

    
    if (arr_length > 2):
        # there is a subdomain 
        domain = split[arr_length - 2] + '.' + split[arr_length - 1]
        
        # check to see if using a ccTLD (i.e. ".co.uk")
        if len(split[arr_length - 1]) == 2 and len(split[arr_length - 1]) == 2:
            # this is using a ccTLD
            domain = split[arr_length - 3] + '.' + domain
        
    return domain


# Module classes
class BingResponse(object):
    """
    Handles connections to the Bing API.
    
    Attributes:
        api_key: The Bing API key to use while querying Bing.
        url: The base URL for the Bing Search API.
        headers: The headers to be used when querying Bing.
        ignored_sites: Sites to not include in the search response.
        query: Keyword query to search by.
        google_link: A link to easily access the query result from Google as
            well.
        response_sites: The response from the Bing API for the given query.
        article_text: The text of the article from which the claim was
            extracted.
        claim_text: The text of the claim retrieved from the article.
        config_file: The path to the application configuration file.
        valid_sites: A subset of response_sites, which was determined as not
            too dissimilar neither too similar, providing a possible candidate
            for a source.
    """
    
    # Initialization methods
    def __init__(self, article_text, claim_text, query, ignored_sites,
                 config_file, api_key):
        """
        Initializes an instance of BingResponse object.
        
        Args:
            article_text: The text of the article from which the claim was
                extracted.
            claim_text: The text of the claim retrieved from the article.
            ignored_sites: Sites to not include in the search response.
            query: Keyword query to search by.
            config_file: The path to the application configuration file.
            api_key: The API key to use when querying Bing.
        """
        self.api_key = api_key
        self.url = 'https://api.cognitive.microsoft.com/bing/v5.0/search'
        self.headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
            'X-MSEdge-ClientID': 'WikipediaSourceFinder'
        }
        
        self.ignored_sites = ignored_sites
        self.query = query
        self.google_link = self.__get_google_link(query, ignored_sites)
        self.response_sites = self.__get_response_sites()
        self.article_text = article_text
        self.claim_text = claim_text
        self.config_file = config_file
        
        self.valid_sites = []
        for website in self.response_sites:
            response_tuple = self.__compare_site(website['url'])
            if response_tuple != None:
                self.valid_sites.append((response_tuple[0],
                                         website['name'],
                                         website['snippet'],
                                         response_tuple[1]))
        
    @staticmethod
    def __get_google_link(keywords, ignored_sites):
        """
        Creates a link to Google search for the query.
        
        Args:
            keywords: Keyword query to search by.
            ignored_sites" Sites to not include in the search response.
        Returns:
            A link to Google search for the query.
        """
        query = keywords
        for (x, site) in enumerate(ignored_sites):
            query += " -site:" + site
        try:
            query = urllib2.quote(unicode(query, 'utf-8'), safe='')
        except KeyError:
            try:
                query = urllib2.quote(query, safe='')
            except:
                query = ""
        except:
            query = ""
            
        query = "https://google.com/search?q=" + query
        return query
    
    def __get_response_sites(self):
        """
        Fetches the Bing API response in JSON format.
        
        Returns:
            Webpage information from the Bing API response.
        """
        payload = {'q' : self.__build_query(self.query, self.ignored_sites),
                   'count': 20}
        response = requests.get(self.url, headers=self.headers, params=payload)
        
        try:
            result = response.json()['webPages']['value']
        except ValueError:
            raise SystemExit
        except:
            result = []
        return result
    
    @staticmethod
    def __build_query(keywords, ignored_sites):
        """
        Returns a Bing API query for given keywords and list of ignored sites.
        
        Args:
            keywords: Keywords generated for the query.
            ignored_sites: Domain names of sites to not search.
        
        Returns:
            A Bing API query.
        """
        query = keywords + " NOT (link:wikipedia.org"
	if 'wikipedia.org' not in ignored_sites:
            query += 'OR site:wikipedia.org'
        length = len(query)
        for site in ignored_sites:
            append = " OR site:" + site
            length += len(append)
            if length <= 1400:
                query += append
            else:
                break 
        query += ")"
    
        return query
    
    def __compare_site(self, url):
        """
        Compares the page and article/claim text.
        
        As a side effect, adds sites that are too similar in text, and thus
        presumably just a copy of the original article, to the list of ignored
        sites for future queries. Updates the configuration file with these.
        
        Args:
            url: The URL of the page to compare.
            
        Returns:
            A tuple in the format (page_url, paragraph) for the most similar 
            paragraph found, or None if the page or paragraph is found to be
            too similar, meaning it is probably copied text from Wikipedia.
        """
        try:
            page_open = urllib2.urlopen(url, timeout=7)
            actual_url = page_open.geturl()
            page = page_open.read()
        except:
            return None
        
        try:
            paragraphs = justext.justext(page, [])
        except:
            return None
        # get the whole page text
        page_text = "\n".join([paragraph.text for paragraph in paragraphs])
        
        # tokenize
        text_tokens = [token for token
                       in gensim.utils.tokenize(page_text, to_lower=True)]
        article_tokens = [token for token
                          in gensim.utils.tokenize(self.article_text,
                                                   to_lower=True)]
        claim_tokens = [token for token
                        in gensim.utils.tokenize(self.claim_text,
                                                 to_lower=True)]
        
        # initialize the dictionary
        dictionary = gensim.corpora.Dictionary([text_tokens, claim_tokens])
        
        # get bag-of-words representations
        text_bow = dictionary.doc2bow(text_tokens)
        article_bow = dictionary.doc2bow(article_tokens)
        claim_bow = dictionary.doc2bow(claim_tokens)
        
        page_similarity = gensim.matutils.cossim(text_bow, article_bow)
        """
        if page_similarity >= 0.95:
            # add page to the list of sites to skip
            root_domain = _extract_root_domain(actual_url)
            config = ConfigParser.ConfigParser()
            config.read(self.config_file)
            cfg_file = open(self.config_file, 'wb')
            try:
                config.get('skipsites', root_domain)
            except ConfigParser.NoOptionError:
                # the page is not yet in defined the file, include
                config.set('skipsites', root_domain, 'true')
                self.ignored_sites.append(root_domain)
            else:
                # the site is included in the file, do not modify the settings
                pass
            
            config.write(cfg_file)
            cfg_file.close()
            
            return None
        
        elif page_similarity < 0.4:
            # the page is too dissimilar - do not include
            return None
        """
        similar_paragraph = ""
        max_similarity = 0
        
        for paragraph in paragraphs:
            paragraph_tokens = gensim.utils.tokenize(paragraph.text,
                                                     to_lower=True)
            paragraph_bow = dictionary.doc2bow(paragraph_tokens)
            
            paragraph_similarity = gensim.matutils.cossim(paragraph_bow,
                                                          claim_bow)
            if max_similarity < paragraph_similarity:
                max_similarity = paragraph_similarity
                similar_paragraph = paragraph.text
            """   
            if max_similarity >= 0.9:
                # the paragraph is too similar, do not include site
                return None
            """
        similar_paragraph = (similar_paragraph[:1000]
                             if len(similar_paragraph) > 1000
                             else similar_paragraph)
            
        return actual_url, similar_paragraph

