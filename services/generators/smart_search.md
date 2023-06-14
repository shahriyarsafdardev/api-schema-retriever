# Smart Search

Smart Search allows you to efficient query large documents without the need for vectorization.

## Function Overview

**Input**: 

- `Query`: A natural language question to be answered using the context of the document
- `Regex Matcher`: Regex that defines what text should be considered to answer the question
- `Document Name`: File name of the document you would like to search through

**Process**: 

1. **Find Matches**: Searches the content for matches to the keywords or regular expressions.
2. **Chunk Creation**: Creates 'chunks' of content around each match using the following strategies: 
    - Creates a maximum size chunk with the keyword in the middle.
    - Creates a maximum size chunk with the keyword at the start.
    - Creates a maximum size chunk with the keyword at the end.
    - Forms a chunk from the previous header to the next header in the content.
3. **Chunk Assessment**: Each chunk is evaluated based on:
    - Asking the input `query` with the following prmopt template:
    
    """
    Use the CONTEXT provided below to respond to the QUERY also provided below.
    
    CONTEXT: {chunk}
    QUERY: {query}

    Option A: Make sure you always only respond to the query with information that is included in the context. If you do not have enough context to conclude the answer, please respond "Not enough context to answer this question". No exceptions.
    
    Option B: Reply in the following json format:
    {
        query_response: "" // response to query using only the information available in the context input,
        confidence: "" // confidence in your response from 1 being, I do not have the necessary context to 5 being I had some context but also made some up, to 10 being I am 100% sure based on the context
    }
    """
4. **Answer Combination**: 
    - 

**Output**: 
- Returns the most confident answer
