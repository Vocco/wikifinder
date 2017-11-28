# Standard imports
import codecs

# Third-party imports
from jinja2 import Environment, FileSystemLoader


# Module functions
def create_report(article_responses, base_url):
    """
    Generates a HTML response for the application run result.
    
    Args:
        article_responses: A list of ArticleResponse objects to be included in
            the report.
        base_url: Base Wikipedia URL to generate links to original articles.
    """
    env = Environment(loader=FileSystemLoader('templates'), autoescape=True)
    template = env.get_template('template.html')
    output_from_parsed_template = template.render(
        articles=article_responses, base_url=base_url)
    
    # to save the results
    with codecs.open("report.html", "wb", 'utf-8') as fh:
        fh.write(output_from_parsed_template)
        