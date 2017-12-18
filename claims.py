# Standard imports
import math

# Third-party imports
import numpy
from gensim.utils import tokenize


# Module functions
def _split_in_sents(string):
    """
    Splits the string into sentences.
    
    Uses a simple heuristic to distinguish between uses of the '.'
    character indicating the end of the sentece and any other uses.
    
    Args:
        string: The string to be split into sentences.
    
    Returns:
        A list of strings that are presumed to be the individual sentences
        of the original string. 
    """
    if isinstance(string, str):
        string = unicode(string, "utf-8")
    
    # split the string by '.' to get naive candidates for sentences
    # remove empty results
    split = filter(lambda x: x != '', string.split("."))
    sentences = []
    sentence_part = []
    
    # build the sentence from parts
    for x, elem in enumerate(split):
        sentence_part.append(elem)
        # we have reached the end of the string
        if x == len(split) - 1:
            sentences.append(".".join(sentence_part))
            break
        
        # move to the next part of the original string
        part_next = split[x+1]
        
        # split the next part to presumed words
        aList = filter(lambda z: z != '', part_next.split(" "))
        
        # the next part of the string is empty
        if len(aList) < 1:
            sentences.append(".".join(sentence_part))
            sentence_part = []
        # heuristic to distinguish between '.' character ending a sentence
        # and any other use
        # other use is indicated by these conditions:
        #   a) the next part of the string contains only one word
        #   b) the next word does not begin with an uppercase letter
        #   c) the last part of the currently considered string begins with
        #      an uppercase letter and is not longer than 4 characters;
        #      this indicates a use for an abbreviation
        elif (len(aList) == 1
              or aList[0].lower() == aList[0]
              or (sentence_part[-1].split(" ")[-1].lower()
                  != sentence_part[-1].split(" ")[-1]
                  and len(sentence_part[-1]) < 5)):
            continue
        else:
            sentences.append(".".join(sentence_part))
            sentence_part = []
            
    return sentences


# Module classes
class Claim(object):
    """
    Encapsulates a single claim from an article.
    
    Attributes:
        title: The original article title.
        text: The text of the claim.
        claim_type: Indicates whether the claim was harvested from the text
            before the [citation needed] template (equal to B) or after it (F).
        article_text: The text of the whole article.
    """
    
    # Class constants
    TAGS = ["very_large", "large", "medium_large", "medium", "medium_small",
            "small", "very_small"]

    def __init__(self, title, text, claim_type, article_text):
        """
        Initializes an instance of a Claim object.
        
        Args:
            title: The original article title.
            text: The text of the claim.
            claim_type: Indicates whether the claim was harvested from the text
                before the [citation needed] template (equal to B) or after it
                (F).
            
        """
        self.title = title
        self.text = text
        self.claim_type = claim_type
        self.article_text = article_text
        
    def get_query(self, dictionary, article_count):
        """
        Gets the keyword query for the claim and stores it.
        
        Args:
            dictionary: A dictionary with token document frequencies.
            article_count: The full count of the articles processed to get the
                'dictionary' dictionary.
        """
        sentences = _split_in_sents(self.text)
    
        tokens, token_tfs = self.__get_tokens_with_tfs(sentences,
                                                       self.article_text)
        token_idfs = self.__get_idfs(tokens, dictionary, article_count)
        tfidfs = []
        
        for x, token in enumerate(tokens):
            tfidfs.append(token_tfs[x] * token_idfs[x])
        
        # scale tfidfs to have values between 0 and 1    
        tfidfs = self.__normalize(tfidfs)
    
        tokens_with_idfs = []        
        for x, token in enumerate(tokens):
            tokens_with_idfs.append((token, tfidfs[x]))
            
        # sort the tokens decreasing based on their tfidf value
        tokens_with_idfs.sort(key=lambda tup: tup[1], reverse = True)
        
        cutoff = self.__get_cutoff(tfidfs)
        
        # get the value of percentile at which to cutoff adding more keywords
        perc = numpy.percentile(tfidfs, cutoff)
        
        prequery = set()
        
        # get the keywords for the query in no particular order
        for token in tokens_with_idfs:
            if token[1] >= perc:
                prequery.add(token[0])
                if (len(prequery) >= 10):
                    break
            else:
                break
                
        query = []
        
        # get the keywords in the order in which the words appeared in the
        # claim
        for token in tokens:
            if token in prequery:
                query.append(token)
                
        if len(query) > 8:
            query = query[:7]
            
        title_array = []
        for keyword in tokenize(self.title):
            title_array.append(keyword)
            
        # append the title to the start of the query, as the position has an
        # effect on the result
        for keyword in reversed(title_array):
            if isinstance(keyword, str):
                keyword = unicode(token, "utf-8")
            
            keyword = keyword.lower()
            keyword = keyword.encode("utf-8")
            
            if keyword not in query:
                query.insert(0, keyword)
        
        self.query = (" ").join(query)
        
    def __get_tokens_with_tfs(self, sentences, text):
        """
        Returns tokens for the text with their weighted term frequencies.
        
        The term frequencies are weighted in the following way:
            
            For claims that are of type "B", the weight is equal to:
                 
                 x + 0.36 * y + 0.216 * z,
            
            where x = 1 if the token appears in the closest sentence to the
            [citation needed] template and 0 otherwise, y is the number of
            occurrences of the token in the second closest sentence and z is
            the number of occurrences in the third closest sentence, if there
            are multiple sentences in the claim.
            
            For claims that are of type "F", the weight is equal to:
            
                x + 0.36 * y + 0.216 * z,
            
            where x = 1 if the token appears in the closest sentence to the end
            of the claim and 0 otherwise, y is the number of occurrences of the
            token in the second closest sentence and z is the number of
            occurrences in the third closest sentence, if there are multiple
            sentences in the claim.
            
            Furthermore if a token appears before the ':' character in the
            claim and it's weight is 0, adds this token with a weight of 0.7.
                
            
        The term frequencies are subsequently scaled to values between 0 and 1,
        so as to minimize the influence of the article size on the computation.
        
        Args:
            sentences: A list of individual sentences.
            text: The full text of the original article.
        
        Returns:
            A tuple of the format (tokens, term_frequencies).
        """
        # Local constants
        COEFFICIENT = 0.6
        
        tokens = []
        token_weights = []
        token_tfs = []
        
        i = 1
        
        # get weights for the tokens in the claim
        while i < 4:
            # weight increment decreases the further away the sentence is from
            # the [citation needed] template, as the semantic weight probably
            # decreases with the distance as well.
            for token in tokenize(sentences[-i]):
                if isinstance(token, str):
                    token = unicode(token, "utf-8")
                
                token = token.lower()
                
                if token in tokens:
                    if i != 1:
                        token_weights[tokens.index(token)] += (
                            1 * (COEFFICIENT ** i))
                else:
                    tokens.append(token.encode("utf-8"))
                    token_tfs.append(0)
                    if i != 1:
                        token_weights.append(float(1 * (COEFFICIENT ** i)))
                    else:
                        token_weights.append(1)
                    
            if sentences[-i] == sentences[0]:
                break
            
            i += 1
            
        if self.claim_type == 'F' and len(sentences) > 3:
            # add the tokens found as an introduction with weight 0.7 if they
            # are not already in the list of tokens
            for token in tokenize(sentences[0]):
                if isinstance(token, str):
                    token = unicode(token, "utf-8")
                
                token = token.lower()
                
                if token not in tokens:
                    tokens.append(token.encode("utf-8"))
                    token_tfs.append(0)
                    token_weights.append(0.7)
            
        # get the actual term frequencies
        for word in tokenize(text):                
            if isinstance(word, str):
                word = unicode(word, "utf-8")
                
            word = word.lower()
            
            for x, token in enumerate(tokens):
                if isinstance(token, str):
                    token = unicode(token, "utf-8")
                    
                token = token.lower()
                
                if token == word:
                    token_tfs[x] += 1
                    break
                
        # get weighted term frequencies
        for x, token in enumerate(tokens):
            token_tfs[x] = math.log(token_tfs[x] + 14, 15.0) * token_weights[x]
                
        return tokens, self.__normalize(token_tfs)
    
    @staticmethod
    def __get_idfs(tokens, dictionary, num_documents):
        """
        Returns a list of IDFs of the corresponding tokens.
        
        The returned list has the same ordering as the tokens input.
        
        Args:
            tokens: A list of the tokens for which to retrieve the inverse
                document frequencies.
            dictionary: A dictionary with token document frequencies.
            num_documents: The full count of the articles processed to get the
                'dictionary' dictionary.
        """
        idfs = []
        for i in tokens:            
            try:
                uni = unicode(i, "utf-8")
                tok_id = dictionary.token2id[uni]
                idf = math.log((1.0 * num_documents)/dictionary.dfs[tok_id],
                                2.0)
                idfs.append(idf)
            except:
                idfs.append(0)
                
        return idfs
    
    @staticmethod
    def __normalize(list_to_normalize):
        """
        Returns the list of numbers scaled to contain values between 0 and 1.
        
        Args:
            list_to_normalize: The list of numbers to be scaled.
        
        Returns:
            The given list normalized to contain only values between 0 and 1.
        """
        list_sum = sum(list_to_normalize)
        
        if list_sum == 0:
            return list_to_normalize

        normalized_list = []
        
        for elem in list_to_normalize:
            normalized_list.append(1.0 * elem/list_sum)
            
        return normalized_list
    
    def __get_cutoff(self, tfidfs):
        """
        Returns TFIDF percentile at which to cut off the addition of keywords.
        
        The function analyzes the rate at which the values of TFIDF for
        different tokens decrease between the 90th and 100th percentile,
        the 80th and 90 percentile, and so on up to the difference between the
        0th and 10th percentile.
        
        It evaluates the overall spread of the values, finds the percentile
        interval at which the rate of decrease is highest and determines the
        ratio of this rate and overall spread. Based on these values, it
        returns a percentile at which the addition of new keywords to the query
        should be stopped.
        
        Args:
            tfidfs: A list of tfidf values for the tokens to be included in the
                query.
                
        Returns:
            The percentile at which the addition of more keywords to the query
            should be stopped.
        """
        perc_value = 90
        cumulative = 0
        cur_max = 0
        position = 0
        
        while (perc_value >= 0):
            diff = (numpy.percentile(tfidfs, perc_value + 10)
                    - numpy.percentile(tfidfs, perc_value))
            cumulative += diff
            if diff > cur_max:
                position = perc_value
                cur_max = diff        
            
            perc_value -= 10
        
        # get the amount of spread between the TFIDF values
        spread = self.__get_tag(cumulative)
        
        # get the ratio of the overall spread and the point of highest rate of
        # the descent of TFIDF values
        break_rate = self.__get_tag(cur_max / cumulative)
        
        # get the percentile at which to cut off the addition of keywords with
        # respect to the point with the highest rate of descent, the rate, and
        # the overall spread of values of the TFIDF values
        cutoff = self.__get_strategy(spread, position, break_rate)
            
        return cutoff
    
    def __get_tag(self, value):
        """
        Returns the tag value of a given spread/descent rate of TFIDF values.
        
        There are seven categories defined.
        
        Args:
            value: The rate of spread/descent of TFIDF values.
            
        Returns:
            The tag of the category to which the rate belongs to.
        """
        tag = "none"
        if value > 0.85:
            tag = self.TAGS[0]
        elif value > 0.7:
            tag = self.TAGS[1]
        elif value > 0.6:
            tag = self.TAGS[2]
        elif value > 0.4:
            tag = self.TAGS[3]
        elif value > 0.3:
            tag = self.TAGS[4]
        elif value > 0.15:
            tag = self.TAGS[5]
        else:
            tag = self.TAGS[6]
            
        return tag
    
    def __get_strategy(self, spread, breaking_point, break_rate):
        """
        Returns the percentile at which the adding of keywords should stop.
        
        Determines the percentile based on the point with the highest rate of
        decrease in the TFIDF values and the ratio of this rate of decrease and
        overall spread.
        
        Note that the percentile computation was acquired empirically.
        
        Args:
            spread: The overall spread of TFIDF values of the potential
                keywords.
            breaking_point: An approximation of the percentile at which the
                TFIDF values decrease the most rapidly. Takes on values from
                {0, 10, 20, ..., 90}.
            break_rate: The ratio of the decrease slope at the point of highest
                decrease and the overall spread.
        """
        strategy = breaking_point
        
        coeff = [6, 5, 4, 4, 4, 3, 2]
        rates = [3, 3, 2, 2, 2, 1, 1]
        
        for i in range(0, 7):
            if spread == self.TAGS[i]:
                for j in range(0, 7):
                    if break_rate == self.TAGS[j]:
                        strategy = self.__lower_by_max(breaking_point,
                                                       coeff[i] * (j + 1),
                                                       rates[i])
                        break
    
        return breaking_point
    
    @staticmethod
    def __lower_by_max(breaking_point, maximum, change):
        """
        Lowers the 'breaking_point' by at most 'maximum'.
        
        If the value of 'breaking_point' - 'value' is negative, tries
        decreasing 'value' by 'change', while 'value' is non-negative.
        
        Args:
            breaking_point: The value to be decreased.
            maximum: The maximum value to attempt to subtract.
            change: The rate of increase in the value being subtracted.
            
        Returns:
            The value of 'breaking_point' lowered by the maximum possible value
            that keeps 'breaking_point' a non-negative number. If this is not
            possible, returns the original value of 'breaking_point'.
        """
        while maximum >= 0:
            if breaking_point - maximum >= 0:
                return breaking_point - maximum
        
            maximum -= change
    
        return breaking_point
                

class ArticleClaims(object):
    """
    Encapsulates claims marked as 'citation needed' from a single article.
    
    Attributes:
        id: The original Wikipedia article ID.
        title: The title of the article.
        text: The plain text of the article enhanced with '$$CNMARK$$' symbols
            in place of the [citation needed] Wikipedia templates.
    """
    
    def __init__(self, article_id, article_title, article_text):
        """
        Initializes an instance of an ArticleClaims object.
        
        Args:
            article_id: The original Wikipedia article ID.
            article_title: The title of the article.
            article_text: The plain text of the article enhanced with
                '$$CNMARK$$' symbols in place of the [citation needed]
                Wikipedia templates.
        """
        self.id = article_id
        self.title = article_title
        self.text = article_text
        self.claims = []
        
    def from_text(self):
        """
        Parses the article text and stores the claims found in it.
        
        Up to 3 claims that are included in a single paragraph are joined, as
        it is likely that they are semantically connected. In such a case, the
        first claim is stored by itself, the second is stored with the first
        one appended, and the third one with the first and second appended.
        These are then treated as separate claims.
        
        A heuristic is used to determine whether a [citation needed] template
        relates to the text before or after it. If a ":" character is found
        close to the left of the template, it is treated as if it relates to
        the text on the right (marked as claim_type "F"). This is usually a
        list or an example. Otherwise, the template is treated as if it relates
        to the text before it (marked as claim_type "B").
        """ 
        lines = self.text.split("\n")
        
        # search for claims in article, paragraphs in wiki markup are divided
        # by "\n"
        for line_no, line in enumerate(lines):
            if "$$CNMARK$$" in line:
                # handle multiple claims
                claims = line.split("$$CNMARK$$")
                    
                for claim_no, claim in enumerate(claims):
                    claim_type = "-"
                    # we have reached the last claim in the paragraph
                    if claim_no == len(claims) - 1:
                        break
                    # ignore short claims, as they do not carry enough semantic
                    # information on their own
                    if len(claim) < 15:
                        continue
                        
                    # claim ends with ":", meaning the citation probably
                    # relates to the next sentence of list
                    if (":" in claim[-4:]):
                        claim_type = "F"
                        
                        # get only the last sentence of the quote, since its
                        # basis is after the citation needed template
                        sents = _split_in_sents(claim)
                        claim = sents[len(sents) - 1]
                        # the next part of paragraph is large, meaning it is
                        # probably a quote or an example
                        if len(claims[claim_no+1]) > 5:
                            claim = "".join([claim, claims[claim_no+1]])
                        
                        # the next part of paragraph is small, the ":" probably
                        # relates to a list that follows, or the next paragraph
                        else:
                            
                            # the next part is a list
                            if "*" in lines[line_no+1]:
                                i = 1
                                while  "*" in lines[line_no+i]:
                                    claim = "".join([claim, lines[line_no+i]])
                                    i += 1
                            # the next part is the next paragraph
                            else:
                                try:
                                    claim = " ".join([claim,
                                                      lines[line_no + 1]])
                                except IndexError:
                                    pass
                                
                    else:
                        # join up to 3 multiple claims in paragraph, as they
                        # are likely semantically connected
                        claim_type = "B"
                        claim = "".join(
                            [claims[claim_no-2] if claim_no-2 >= 0 else "",
                             claims[claim_no-1] if claim_no-1 >= 0 else "",
                             claims[claim_no]])

                    self.claims.append(Claim(self.title, claim, claim_type,
                                             self.text))    
    
