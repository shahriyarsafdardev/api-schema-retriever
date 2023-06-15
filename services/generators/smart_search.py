import logging
from services.helpers.s3 import read_object
from services.helpers.json_loader import load_json
from urllib.parse import quote, urlparse, urlunparse
import re

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(levelname)s - %(message)s')


def detect_links(text, connector):
    link_pattern = r"(?:(?<=\s)|(?<=^))(?:http|\/)[^\s\"'\)\]`]+"
    links = [(m.start(), m.group()) for m in re.finditer(link_pattern, text)]

    def is_valid_url(url):
        # base_url_components = list(filter(lambda x: x not in ['https:', 'www', 'com', ''], re.split('\.|-|/',connector['base_url'])))

        if url.endswith(('.jpg', '.png', '.jpeg', '.gif', '.ico')):
            return False

        if len(url) <= 2:
            return False
        if '\\' in url:
            return False
        if '\ufffd' in url:
            return False
        if '/' not in url:
            return False
        # if len([c for c in url if c.isalpha()]) < 3:
        #     return False
        # if "//github.com" in url:
        #     return False
        # if url.startswith('/'):
        #     return True

        # has_base_url_substring = any(substr in url for substr in base_url_components)
        # if has_base_url_substring:
        #     return True

        return True

    return [(start, link) for start, link in links if is_valid_url(link)]


def detect_auth(text, connector):
    auth_pattern = r"\s[Aa]uth"
    return [(m.start(), m.group()) for m in re.finditer(auth_pattern, text)]


def detect_get(text, connector):
    get_pattern = r"[^\w][Gg][Ee][Tt][^\w]"
    return [(m.start(), m.group()) for m in re.finditer(get_pattern, text)]


def smart_search_new_new(matcher, content, connector, context_length=150):
    logging.info("Starting smart_search_new_new")
    matches = matcher(content, connector)
    contexts = [get_context_str(match, content, context_length)
                for match in matches]

    # Detect links within each context
    links_in_context = [detect_links(context, connector)
                        for context in contexts]

    # If you want to get the link strings only and not their start positions, you can do the following:
    link_strs_in_context = [[link[1] for link in links]
                            for links in links_in_context]

    # Flatten the list of lists to a single list
    all_links = [link for sublist in link_strs_in_context for link in sublist]

    # Remove URL parameters from the links
    clean_links = []
    for link in all_links:
        try:
            url_parts = list(urlparse(link))
            url_parts[4] = ""  # Empty the query string
            clean_link = urlunparse(url_parts)
            clean_links.append(clean_link)
        except Exception as e:
            logging.info(f"Error while parsing {link}")

    logging.info(
        f"Finished smart_search_new_new, found {len(clean_links)} links")
    return sorted(list(set(clean_links)))


def get_context_str(match, content, context_length=150, verbose=False):
    match_start, match_str = match

    # Find the nearest whitespace before the left context_length
    left = match_start - context_length
    if left > 0:
        while left > 0 and content[left] not in (' ', '\t', '\n'):
            left -= 1
    else:
        left = 0

    # Find the nearest whitespace after the right context_length
    right = match_start + len(match_str) + context_length
    if right < len(content):
        while right < len(content) and content[right] not in (' ', '\t', '\n'):
            right += 1
    else:
        right = len(content)

    # Extract the context string
    context = content[left:right]

    if verbose:
        logging.debug(
            f"Context:\n\033[31m{content[left:match_start]}\033[0m\033[34m{content[match_start:match_start + len(match_str)]}\033[0m\033[31m{content[match_start + len(match_str):right]}\033[0m\n")

    return context


def clean(text):
    logging.info(f"Started removing new lines from text")
    cleaned_text = text.replace('\n', '; ')
    logging.info(f"Finished removing new lines from text")
    return cleaned_text


if __name__ == "__main__":
    logging.info("Starting smart_search.py")
    connectors = load_json('data/airbyte_connectors.json', local=True)

    successful_connectors = 0

    for i in range(0, 300):
        logging.info("Loaded connectors")
        connector = connectors[i]
        logging.info(f"Connector: {connector['name']}")
        logging.info(
            f"Connector: {quote(connector['base_url'], safe='') + '-bulk-concise' + '.md'}")
        bulk_concise = read_object(
            quote(connector['base_url'], safe="") + '-bulk-concise' + '.md')
        if bulk_concise is None:
            logging.error(
                f"Could not read bulk_concise for {connector['name']}")
            continue
        logging.info(f"Read bulk_concise")
        # bulk_concise = clean(bulk_concise)
        result = smart_search_new_new(detect_get, bulk_concise, connector)
        if result != []:
            successful_connectors += 1

        logging.info("\n".join(result))

    logging.info(
        f"Finished smart_search.py, found {successful_connectors} connectors")
