from services.helpers.s3 import read_object
from services.helpers.json_loader import load_json
from urllib.parse import quote

import re

# gpt-4 = 8,000 tokens = 32,000 characters = 320 snippets

def smart_search(regex_matcher, content):
    matches = regex_matcher.finditer(content) 

    print(f"Found {len(list(matches))}")
    
    return list(matches) 

def get_context(match, content, context_length=50, verbose=False):
    start = max(0, match.start() - context_length)
    end = min(len(content), match.end() + context_length)
    if verbose:
        print(f"Context:\n\033[31m{content[start:match.start()]}\033[0m\033[34m{content[match.start():match.end()]}\033[0m\033[31m{content[match.end():end]}\033[0m\n")
    return content[start:end]

connectors = load_json('data/airbyte_connectors.json', local=True)
# regex_queries = [r"REST API", r"\s[aA]uth", r"\s[aA]uthentication", r"\s[pP]aginat", r"\s[rR][eE][sS][tT]", r"\s[aA][pP][iI]"]
regex_queries = [r"[aA][pP][iI]"]

results = {query: 0 for query in regex_queries}
match_counts = {query: 0 for query in regex_queries}

total_connectors = 0  # Initialize total connectors to 0

for connector in connectors:
    bulk_concise = read_object(quote(connector['base_url'], safe="") + '-bulk-concise' + '.md')
    
    # Check if bulk_concise is a string before processing
    if isinstance(bulk_concise, str):
        # Only count the connector in the total if bulk_concise has more than 10 lines
        # print(f"Connector: {connector['name']}")
        if len(bulk_concise.split('\n')) > 10:  
            total_connectors += 1

            for query in regex_queries:
                matches = smart_search(re.compile(query, re.IGNORECASE), bulk_concise)
                match_counts[query] += len(matches)
                if len(matches) > 0:
                    results[query] += 1
                    for match in matches:
                        get_context(match, bulk_concise)

print(f"Total connectors: {total_connectors}")
for query, count in results.items():
    avg_matches = match_counts[query] / total_connectors if total_connectors > 0 else 0
    print(f"{(count / total_connectors) * 100}% of connectors have at least one instance of '{query}'")
    print(f"Average number of matches for '{query}': {avg_matches}")
    print(f"\n")
