import os, re, collections, time, itertools
import mysql.connector

##### ENVIRONMENT VARIABLES #####
from dotenv import load_dotenv
load_dotenv()
SQL_HOSTNAME = os.environ["SQL_HOSTNAME"]
SQL_USERNAME = os.environ["SQL_USERNAME"]
SQL_PASSWORD = os.environ["SQL_PASSWORD"]

def connect_sql(database="thaicorpus"):
    config = {'user': SQL_USERNAME,
        'password': SQL_PASSWORD,
        'host': SQL_HOSTNAME,
        'database': database} # name of database
    con = mysql.connector.connect(**config)
    cursor = con.cursor(buffered=True)
    return con, cursor

################################################################################
#####   SEARCH BY WORD FUNCTION
################################################################################

TOTAL_TOKENS_DIC = {
    'thairath': 3534308, 
    'dailynews': 3403007, 
    'matichon': 1883713, 
    'NHK': 934674, 
    'twitter': 6140618,
    'pantip': 5931778
}

TOTAL_TYPES_DIC = {
    'thairath': 3534308, 
    'dailynews': 3403007, 
    'matichon': 1883713, 
    'NHK': 934674, 
    'twitter': 6140618,
    'pantip': 91160}

def search_by_word(query:str, sources:list, n_left:int, n_right:int, is_multiple_word=False):
    """
    Params
    ------
        query : one word or comma delimited words, e.g. อร่อย|มาก
        sources : list of datasources [twitter, NHK]
        n_left : window size of n-gram
        is_multiple_word : whether use multiple words in search

    Returns
    ------- 
        ngrams : list of left/right ngram ranking : [[left_bigram, count, right_bigram, count],...] 30 lines
        wf_time : list of [source, total_wf, searchtime] e.g.[[twitter, 203.12, 2.1],[pantip, 140.31, 1.2]]
    """

    ##### initialize #####
    start_time = time.time()
    con, cursor = connect_sql('thaicorpus')
    total_tokens = 0 # num of all tokens
    wf_in_all = 0 # num of query in all sources 
    ngram_L = collections.Counter() 
    ngram_R = collections.Counter()
    wf_time = [] # [[source, wf, searchtime],... [total, total wf, total search time]]

    ##### iterate each source #####
    for source in sources:
        start_time_source = time.time() # start time of each source
        total_tokens += TOTAL_TOKENS_DIC[source]
        wf_in_source = 0 # frequency in the source
        query = query.replace('__','<s>') # __|เดินทาง -> <s>|เดินทาง
        query = query.replace('[start]','<start>').replace('[end]','<end>') # [start]|เดินทาง -> <start>|เดินทาง
        splitted_query = query.split('|')
        num_of_query = len(splitted_query)
        #print(query)
        # get JSON array of document index and Join with main table
        if num_of_query == 1: # single word search
            stmt1 = f"SELECT @{source} := IDs FROM {source}_index WHERE word = '{query}' LIMIT 1;" # get JSON array of document index, assign to variable @{source}
            stmt2 = f"SELECT tokens FROM JSON_TABLE(@{source}, '$[*]' COLUMNS(ID INT PATH '$')) AS temp LEFT JOIN {source} ON temp.ID = {source}.ID;" # join
            cursor.execute(stmt1)
            cursor.execute(stmt2)
            print(stmt1, stmt2, sep='\n')
        elif num_of_query == 2: # use bigram index instead
            stmt1 = f"SELECT @{source} := IDs FROM {source}_index_bigram WHERE word = '{query}' LIMIT 1;"
            stmt2 = f"SELECT tokens FROM JSON_TABLE(@{source}, '$[*]' COLUMNS(ID INT PATH '$')) AS temp LEFT JOIN {source} ON temp.ID = {source}.ID;"
            cursor.execute(stmt1)
            cursor.execute(stmt2)
            print(stmt1, stmt2, sep='\n')
        elif num_of_query == 3: # Join bigrams 2 times
            query1 = '|'.join(splitted_query[0:2]) # [ไป, ไหน, ดี] -> 'ไป|ไหน'
            query2 = '|'.join(splitted_query[1:3]) # [ไป, ไหน, ดี] -> 'ไหน|ดี'
            stmt1 = f"SELECT @{source}1 := IDs FROM {source}_index_bigram WHERE word = '{query1}' LIMIT 1;"
            stmt2 = f"SELECT @{source}2 := IDs FROM {source}_index_bigram WHERE word = '{query2}' LIMIT 1;"
            stmt3 = f"SELECT tokens FROM JSON_TABLE(@{source}1, '$[*]' COLUMNS(ID INT PATH '$')) AS temp1\
                        INNER JOIN (SELECT ID FROM JSON_TABLE(@{source}2, '$[*]' COLUMNS(ID INT PATH '$')) AS tt) AS temp2 ON temp1.ID = temp2.ID\
                        LEFT JOIN {source} ON temp2.ID = {source}.ID;"
            cursor.execute(stmt1)
            cursor.execute(stmt2)
            cursor.execute(stmt3)
            print(stmt1,stmt2,stmt3, sep='\n')
        elif num_of_query > 3:
            for i in range(num_of_query-1):
                temp_query = '|'.join(splitted_query[i:i+2])
                stmt = f"SELECT @{source}{i} := IDs FROM {source}_index_bigram WHERE word = '{temp_query}' LIMIT 1;" # get document index
                cursor.execute(stmt)
                print(stmt)
                if i == 0:
                    stmt_join = f"SELECT tokens FROM JSON_TABLE(@{source}0, '$[*]' COLUMNS(ID INT PATH '$')) AS temp0 "
                elif i > 0:
                    stmt_join += f"INNER JOIN (SELECT ID FROM JSON_TABLE(@{source}{i}, '$[*]' COLUMNS(ID INT PATH '$')) AS tt) AS temp{i} ON temp0.ID = temp{i}.ID "            
            stmt_join += f"LEFT JOIN {source} ON temp{i}.ID = {source}.ID;"
            print(stmt_join)
            cursor.execute(stmt_join)

        ##### make ngram of each record #####
        # if multiple words, check whether query "w1|w2" is in the result 
        for record in list(cursor): # list of tuples [(tokens,), (tokens,)...] where tokens is like "<start>|ไป|โรงเรียน|พรุ่งนี้|<end>" 
            tokens = '<start>|'*n_left + record[0] + '|<end>'*n_right # add <start>|<start>|... AND ...|<end>|<end>
            if is_multiple_word and query not in tokens:
                continue
            # add word frequency
            wf_in_source += tokens.count(f'|{query}|')

            ### left n-gram ###  replace('|','\|') for regex
            pattern = re.compile(r'\|(' + r'[^\|]+?\|'*(n_left-1) + r'[^\|]+?)\|' + query.replace('|','\|')+r'\|') # if n=3, ngram pattern = |(...|...|...)|query|
            left_contexts = re.findall(pattern, tokens) 
            for left in left_contexts:
                ngram = left.replace('|',' ') + ' ' + query # captured context + query e.g. อาหาร นี้ อร่อย|ไหม
                ngram = ngram.replace('<s>','__').replace('<start>','[start]').replace('<end>','[end]') # <start> has problem in HTML
                ngram = re.sub(r'(?: ?\[start\])+', '[start]', ngram) # [start] [start] [start]|word -> [start]|word
                ngram_L[ngram.replace('<s>','__')] += 1 # replace <s>

            ### right n-gram ###
            pattern = re.compile(r'\|'+query.replace('|','\|') + r'\|([^\|]+?' + r'\|[^\|]+?'*(n_right-1) + r')\|') # ngram pattern = |query|(...|...)| 
            right_contexts = re.findall(pattern, tokens+'<end>|'*n_right) 
            for right in right_contexts:
                ngram = query + ' ' + right.replace('|', ' ') # q1|q2 word word
                ngram = ngram.replace('<s>','__').replace('<start>','[start]').replace('<end>','[end]') # <end> has problem in HTML
                ngram = re.sub(r'(?:\[end\] ?)+', '[end]', ngram) # word|[end] [end] [end] -> word|[end]
                ngram_R[ngram] += 1 
        
        # word frequency per 1M & search time of one source
        wf_time.append([source, round(wf_in_source / TOTAL_TOKENS_DIC[source] * 1000000, 2), round(time.time()-start_time_source, 2)])
        wf_in_all += wf_in_source

    # make ranked & concatenated ngam list : [[left_bigram, count, right_bigram, count],...] 30 lines
    ngrams = []
    for L, R in itertools.zip_longest(ngram_L.most_common(30), ngram_R.most_common(30)):
        if L == None:
            ngrams.append(['',''] + list(R))
        elif R == None:
            ngrams.append(list(L) + ['',''])
        else:
            ngrams.append(list(L) + list(R))
    # total word frequency
    wf_time.append(['total', round(wf_in_all / total_tokens * 1000000, 2), round(time.time()-start_time, 2)])
    #print(ngrams)
    return ngrams, wf_time

################################################################################
#####   SEARCH BY STRING FUNCTION (FROM TOP PAGE)
################################################################################

def search_by_string(query:str, sources:list, is_regex=False, max_len=500):
    """
    Params
    ------
        query : any string, may have [start] or [end] like "[start]โรงเรียน"
        sources : data sources. consistent to the names of SQL tables
        is_regex : if "RegEx" is checked, use regular expression

    Returns
    -------
        result : list of [sentence, datasource] that contain query (highlighted with <span class="red"></span>)
    """
    con, cursor = connect_sql('thaicorpus')
    result = [] # list of [sentence, datasource]
    
    # determine mode
    if is_regex:
        mode = 'regex'
    elif query.startswith('[start]'): 
        mode = 'start'
        query = query.replace('[start]', '') # "[start]โรงเรียน" -> "โรงเรียน"
    elif query.endswith('[end]'): # query = แล้ว[end], SQL wildcard % only before query
        mode = 'end'
        query = query.replace('[end]', '')
    else:
        mode = 'any'

    ##### iterate sources #####
    for source in sources:
        # variable "mode" is used for extracting sentences : start (query%), end(%query), any(%query%)

        if mode == 'regex':
            stmt = f"SELECT full_text FROM {source} WHERE full_text REGEXP '{query}' LIMIT {max_len};"
        elif mode == 'start': # query = [start]เมื่อ, SQL wildcard % only after query
            stmt = f"SELECT full_text FROM {source} WHERE full_text LIKE '{query}%' LIMIT {max_len};"
        elif mode == 'end': # query = แล้ว[end], SQL wildcard % only before query
            stmt = f"SELECT full_text FROM {source} WHERE full_text LIKE '%{query}' LIMIT {max_len};"
        elif mode == 'any': # neither [start] nor [end]
            stmt = f"SELECT full_text FROM {source} WHERE full_text LIKE '%{query}%' LIMIT {max_len};"
        print(stmt)
        cursor.execute(stmt)

        # append SQL result to list
        for record in list(cursor): # [(full_text,), (full_text,), ...]
            text = record[0]
            if mode == 'regex':
                sentences = re.findall(re.compile(r'(?:^|\s).{0,60}' + query + r'.{0,60}(?:$|\s)'), text)
            elif mode == 'start':
                sentences = re.findall(r'^' + query + r'.{0,100}(?:$|\s)', text) # "query...($| )"
            elif mode == 'end':
                sentences = re.findall(r'(?:^|\s).{0,100}' + query + r'$', text) # "(^| )...query"
            elif mode == 'any':
                sentences = re.findall(r'(?:^|\s).{0,60}' + query + r'.{0,60}(?:$|\s)', text) # "(^| )...query...($| )"
            result += [[highlight(sentence, query, is_regex), source] for sentence in sentences]
            if len(result) >= max_len:
                return result[:max_len]
    #print(result)
    return result

################################################################################
#####   RESULT OF SEARCH BY WORD -> SEARCH BY STRING FUNCTION (FROM TOP PAGE)
################################################################################

def search_by_string_from_word(query:str, sources:list, max_len=500):
    """
    jump from the result of SEARCH BY WORD
    1. in SQL, the same process of SEARCH BY WORD (use inverted index)
    2. in python, the same process of SEARCH BY STRING (use Regex to extract)

    Params
    ------
        query : one word or comma delimited words, e.g. อร่อย|มาก
        sources : list of datasources [twitter, NHK]

    Returns
    -------
        result : list of [sentence, datasource] that contain query (highlighted with <span class="red"></span>)
    """

    ##### initialize #####
    con, cursor = connect_sql('thaicorpus')
    result = [] # list of [sentence, datasource]
    
    # 1. query for use inverted index (contain | , <start> <s>)
    query = query.replace('__','<s>') # __|เดินทาง -> <s>|เดินทาง
    query = query.replace('[start]','<start>').replace('[end]','<end>') # [start]|เดินทาง -> <start>|เดินทาง
    splitted_query = query.split('|') # [ไป, ไหน]
    num_of_query = len(splitted_query)

    # 2. query for regex match (contain neither | nor <>)
    # determine regex mode too
    if query.startswith('<start>'):
        mode = 'start'
        regex_query = query.replace('<start>','') # "<start>|เมื่อ" -> "|เมื่อ"
    elif query.endswith('<end>'):
        mode = 'end'
        regex_query = query.replace('<end>','')
    else:
        mode = 'any'
        regex_query = query
    regex_query = regex_query.replace('|','').replace('<s>',' ') # "|ไป|<s>|ไหน" -> "ไป ไหน"

    ##### iterate each source #####  almost same as word search -> when JOIN, use "full_text" instead
    for source in sources:
        
        #print(query)
        ### get JSON array of document index and Join with main table ###
        if num_of_query == 1: # single word search
            stmt1 = f"SELECT @{source} := IDs FROM {source}_index WHERE word = '{query}' LIMIT 1;" # get JSON array of document index, assign to variable @source
            stmt2 = f"SELECT full_text FROM JSON_TABLE(@{source}, '$[*]' COLUMNS(ID INT PATH '$')) AS temp LEFT JOIN {source} ON temp.ID = {source}.ID;" # join
            cursor.execute(stmt1)
            cursor.execute(stmt2)
        elif num_of_query == 2: # use bigram index instead
            stmt1 = f"SELECT @{source} := IDs FROM {source}_index_bigram WHERE word = '{query}' LIMIT 1;"
            stmt2 = f"SELECT full_text FROM JSON_TABLE(@{source}, '$[*]' COLUMNS(ID INT PATH '$')) AS temp LEFT JOIN {source} ON temp.ID = {source}.ID;"
            cursor.execute(stmt1)
            cursor.execute(stmt2)
        elif num_of_query == 3: # Join bigrams 2 times
            query1 = '|'.join(splitted_query[0:2]) # [ไป, ไหน, ดี] -> 'ไป|ไหน'
            query2 = '|'.join(splitted_query[1:3]) # [ไป, ไหน, ดี] -> 'ไหน|ดี'
            stmt1 = f"SELECT @{source}1 := IDs FROM {source}_index_bigram WHERE word = '{query1}' LIMIT 1;"
            stmt2 = f"SELECT @{source}2 := IDs FROM {source}_index_bigram WHERE word = '{query2}' LIMIT 1;"
            stmt3 = f"SELECT full_text FROM JSON_TABLE(@{source}1, '$[*]' COLUMNS(ID INT PATH '$')) AS temp1\
                        INNER JOIN (SELECT ID FROM JSON_TABLE(@{source}2, '$[*]' COLUMNS(ID INT PATH '$')) AS tt) AS temp2 ON temp1.ID = temp2.ID\
                        LEFT JOIN {source} ON temp2.ID = {source}.ID;"
            cursor.execute(stmt1)
            cursor.execute(stmt2)
            cursor.execute(stmt3)
        elif num_of_query > 3: # generalize of num = 3
            for i in range(num_of_query-1):
                temp_query = '|'.join(splitted_query[i:i+2])
                stmt = f"SELECT @{source}{i} := IDs FROM {source}_index_bigram WHERE word = '{temp_query}' LIMIT 1;" # get document index
                cursor.execute(stmt)
                if i == 0:
                    stmt_join = f"SELECT full_text FROM JSON_TABLE(@{source}0, '$[*]' COLUMNS(ID INT PATH '$')) AS temp0 "
                elif i > 0:
                    stmt_join += f"INNER JOIN (SELECT ID FROM JSON_TABLE(@{source}{i}, '$[*]' COLUMNS(ID INT PATH '$')) AS tt) AS temp{i} ON temp0.ID = temp{i}.ID "            
            stmt_join += f"LEFT JOIN {source} ON temp{i}.ID = {source}.ID;"
            cursor.execute(stmt_join) # candidates of full text

        # append SQL result to list
        # find query + context with boundary
        # if not found (= too long context), use fixed char number instead
        # use regex_query "w1w2w3" instead query = "w1|w2|w3"
        sql_results = list(cursor)
        if sql_results == []:
            continue
        for i, record in enumerate(sql_results): # [(full_text,), (full_text,), ...]
            text = record[0]
            if regex_query not in text: # if the candidate does not contain query
                continue
            if mode == 'start':
                sentences = re.findall(r'^' + regex_query + r'.{0,100}(?:$|\s)', text) # "query...($| )"
                if sentences == []:
                    sentences = re.findall(r'^' + regex_query + r'.{0,80}', text)
            elif mode == 'end':
                sentences = re.findall(r'(?:^|\s).{0,100}' + regex_query + r'$', text) # "(^| )...query"
                if sentences == []:
                    sentences = re.findall(r'.{0,80}' + regex_query + r'$', text)
            elif mode == 'any':
                sentences = re.findall(r'(?:^|\s).{0,60}' + regex_query + r'.{0,60}(?:$|\s)', text) # "(^| )...query...($| )"
                if sentences == []:
                    sentences = re.findall(r'.{0,50}' + regex_query + r'.{0,50}', text)
            result += [[highlight(sentence, regex_query, is_regex=False), source] for sentence in sentences]
            if len(result) >= max_len:
                return result[:max_len]
    return result

def highlight(text:str, keyword:str, is_regex=False):
    """
    highlight keyword in the text
    wrapped with <span class="red">...</span>
    """
    if keyword == "":
        return text
    if is_regex == False:
        return text.replace(keyword, f'<span class="red">{keyword}</span>')
    else:
        pattern = re.compile(f'({keyword})')
        text = re.sub(pattern, r'<span class="red">\1</span>', text)
        return text        