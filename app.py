from flask import Flask, request, render_template, jsonify
import os, sys, re, collections, csv, glob, time, itertools
import mysql.connector

### pythainlp
from pythainlp.corpus.common import thai_words
from pythainlp import word_tokenize, Tokenizer
from pythainlp.corpus import thai_stopwords
PYTHAI_STOPWORDS = thai_stopwords()

### word2vec
from gensim.models import word2vec, KeyedVectors
MODEL_THAIRATH = KeyedVectors.load_word2vec_format('data/thairath_restricted.bin', unicode_errors='ignore', binary=True)

import pandas as pd
import numpy as np
from PIL import Image
from wordcloud import WordCloud
from thaig2p import g2p, decode, clean

### import corpus.py
from corpus import *

### instantiate app
class CustomFlask(Flask):
	jinja_options = Flask.jinja_options.copy()
	jinja_options.update(dict(
		variable_start_string='((',
		variable_end_string='))',
	))

app = CustomFlask(__name__)


@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

##### ENVIRONMENT VARIABLES #####
from dotenv import load_dotenv
load_dotenv()

### word2vec
#model_daily = KeyedVectors.load_word2vec_format('static/wv_daily.bin', unicode_errors='ignore', binary=True)

################################################################################
#####   CORPUS
################################################################################

@app.route("/", methods=['GET', 'POST'])
def top_page():
    # top page
    if request.method == 'GET':
        return render_template('result.html')

    ########## Ajax ##########
    elif request.method == 'POST':
        try:
            #app.logger.info(request.form) # logging data to nohup.out
            sources = request.form.getlist('sources[]') # list of data sources [source_twitter, source_pantip]
            sources = [s.replace('source_', '') for s in sources] # replace to [twitter, pantip]

            if request.form['media'] == 'mobile': # if mobile, show fewer results
                max_len = 300 # for string search
            else:
                max_len = 500

            ########## TOP PAGE -> SEARCH BY ONE WORD ##########
            if request.form['mode'] == 'word':
                n_left = int(request.form['n_left']) # left window size 1-4
                n_right = int(request.form['n_right']) # right window size 1-4
                use_multiple_words = request.form['use_multiple_words'] == 'true'
                
                ### ONE WORD ###
                if request.form['input2'].strip() == '': # only one input
                    query = request.form['input1']
                    # ngrams = concatenated and sorted list [[left_bigram, count, right_bigram, count],...] 30 lines
                    # word_freq = list of [source, wf, searchtime] : [[pantip, 134, 12],[total, 293, 40]]
                    ngrams, word_freq = search_by_word(query, sources, n_left, n_right, use_multiple_words)
                    
                    return jsonify({
                        'ngrams1': ngrams, 
                        'word_freq1': word_freq,
                        'sources': sources
                    })
                    
                ### TWO WORDS ###
                else:
                    query1 = request.form['input1']
                    query2 = request.form['input2']
                    ngrams1, word_freq1 = search_by_word(query1, sources, n_left, n_right)
                    ngrams2, word_freq2 = search_by_word(query2, sources, n_left, n_right)
                    return jsonify({
                        'ngrams1': ngrams1, 
                        'ngrams2': ngrams2, 
                        'word_freq1': word_freq1,
                        'word_freq2': word_freq2,
                        'sources': sources
                    })

            ########## TOP PAGE -> SEARCH BY STRING ##########
            elif request.form['mode'] == 'string':
                is_regex = request.form['is_regex'] == 'true' 

                ### ONE STRING ###
                if request.form['input2'].strip() == '': # only one input
                    query = request.form['input1']
                    results = search_by_string(query, sources, is_regex=is_regex, max_len=max_len)
                    return jsonify({
                        'results1': results, # the list of [sentence, datasource], sentence is HTML e.g. ไป<span>โรงเรียน</span>
                        'sources': sources
                    })

                ### TWO STRINGS ###
                else:
                    query1 = request.form['input1']
                    query2 = request.form['input2']
                    results1 = search_by_string(query1, sources, is_regex=is_regex, max_len=max_len) 
                    results2 = search_by_string(query2, sources, is_regex=is_regex, max_len=max_len) 
                    return jsonify({
                        'results1': results1,
                        'results2': results2,
                        'sources': sources
                    })

            ########## RESULT OF SEARCH BY WORD -> SEARCH BY STRING ##########
            elif request.form['mode'] == ('word_to_string'):
                query = request.form['input3']
                results = search_by_string_from_word(query, sources, max_len=max_len)
                return jsonify({
                    'results1': results, # the list of [sentence, datasource], sentence is HTML e.g. ไป<span>โรงเรียน</span>
                    'sources': sources
                })

        except Exception as e:
            print(e)
            return render_template('corpus.html')


###### OTHER PAGES ######
@app.route("/data", methods=['GET', 'POST'])
def page_date():
    return render_template('data.html')

@app.route("/true", methods=['GET', 'POST'])
def page_true():
    if request.method == 'GET':
        return render_template('true.html')
    else:
        drama = request.form['drama']
        df = pd.read_json(f'static/{drama}.json')
        df = df[(df.text.str.contains('น่ะ'))|df.text.str.contains('หน่ะ')|df.text.str.contains('หนะ')]
        df = df[['text','part','page','allpage','url']].values.tolist()
        df = [[highlight(x[0], 'น่ะ')] + x[1:] for x in df]
        df = [[highlight(x[0], 'หนะ')] + x[1:] for x in df]
        df = [[x[0].replace('\n', '<br>')] + x[1:] for x in df]
        #print(df[0][0])
        return render_template('true_result.html', df=df, drama=drama)

################################################################################
#####   TOKENIZER
################################################################################

@app.route("/tokenize", methods=['GET', 'POST'])
def page_tokenize():
    if request.method == 'GET':
        return render_template('tokenize.html', result=None)
    else:
        text = request.form.get('text', '').strip()
        textfile = request.files.get('file', None)
        custom_dict = request.form['custom_dict']
        if textfile:
            text = textfile.read().decode(encoding='utf-8') # convert to str
        #print(request.form)
        ### shrink whitespace
        if request.form['whitespace'] in ['shrink', 'shrink2']:
            text = re.sub(r'[ \u00a0\xa0\u3000\u2002-\u200a\t]+', ' ', text) # e.g. good  boy -> good boy
            text = re.sub(r'[\r\u200b\ufeff]', '', text) # remove non-breaking space
        if request.form['whitespace'] == 'shrink2':
            text = re.sub(r' ๆ', 'ๆ', text)
        #print(request.form)
        ### punctuation
        if request.form['punctuation'] == 'remove':
            text = re.sub(r'[“”„\"‘’`\'\[\]\(\),;:]', '', text)
        ### remove others
        text = re.sub(r'https?://[^\s]+((?=\s)|(?=$))', '', text) # remove URL
        text = re.sub(r'</?.+?>', '', text) # remove tag
        ### tokenize
        to_keepspace = 'keepspace' in request.form # boolean
        if request.form['engine'] == 'attacut': # if attacut, ignore custom dict 
            tokens = [word_tokenize(line, keep_whitespace=to_keepspace, engine='attacut') for line in text.split('\n')]
        elif custom_dict.strip() != '': # has custom dict
            WORD_SET = thai_words() | set(re.split(r'[,\s\t]+', custom_dict)) # add custom dict
            custom_tokenizer = Tokenizer(WORD_SET)
            tokens = [custom_tokenizer.word_tokenize(line) for line in text.split('\n')] # no "keep_whitespace"
            if not to_keepspace:
                tokens = [[t for t in line if t != ' '] for line in tokens]
        else: # newmm, no custom dict
            tokens = [word_tokenize(line, keep_whitespace=to_keepspace) for line in text.split('\n')]
        token_num = sum([len([x for x in line if x.strip() != '']) for line in tokens]) # dont count ' '
        ### delimiter
        delimiter = {'vbar':'|','comma':',','semicolon':';','tab':'\t','space':' '}[request.form['delimiter']]
        tokens = [delimiter.join(line) for line in tokens] # join each line
        # return original text too
        return render_template('tokenize.html', result='\n'.join(tokens), token_num=token_num, text=text, custom_dict=custom_dict)

################################################################################
#####   G2P
################################################################################

@app.route("/g2p", methods=['GET','POST'])
def page_g2p():
    if request.method == 'GET':
        return render_template('g2p.html', result=None)
    else:
        text = request.form['text']
        transcription = request.form['transcription']
        radio_i = {'haas':0, 'ipa':1}[transcription] # use for send back haas/ipa
        # try to get phone
        try:
            undecoded = g2p(text, decoded=False)
            result = decode(undecoded, transcription)
        except:
            undecoded = ''
            result = 'SORRY, ERROR HAPPENED'
        # record log
        try:
            with open('g2plog.csv', 'a', encoding='utf8') as f:
                w = csv.writer(f)
                w.writerow([text.strip(), undecoded])
        except:
            pass
        return render_template('g2p.html', result=result, text=text, radio_i=radio_i)

################################################################################
#####   WORDCLOUD
################################################################################

@app.route("/wordcloud", methods=['GET','POST'])
def page_wordcloud():
    if request.method == 'GET':
        return render_template('wordcloud.html')
    else:
        s = time.time()
        font = request.form['font']
        text = request.form.get('text', '') # one string
        textfile = request.files.get('file', None)
        to_tokenize = 'tokenize' in request.form
        to_remove_stop = 'remove_stop' in request.form
        #print(request.form)
        try:
            if textfile:
                text = textfile.read().decode(encoding='utf-8') # convert to str
            if to_tokenize:
                tokens = clean(text)
                tokens = word_tokenize(tokens, keep_whitespace=False)
                tokens = ' '.join(tokens) # rejoin to one string
            else:
                tokens = re.sub(r'[\s\t\n,]+', ' ', text) # already one string
            ### stopwords
            stopwords = set(re.split(r'[\s\t,]+', request.form['stopwords']))
            if to_remove_stop:
                stopwords |= PYTHAI_STOPWORDS
            print(time.time()-s)
            ### get bgcolor
            bgcolor = request.form['bgcolor16']
            if not re.match(r'#[\dA-Fa-f]{6}', bgcolor):
                bgcolor = request.form['bgcolor']
            if bgcolor == 'transparent':
                bgcolor = None
            ### get mask shape
            maskshape = request.form['maskshape']
            if maskshape == 'none':
                mask = None
            else:
                mask = np.array(Image.open(f'./static/img/mask_{maskshape}.png'))
            ### generate
            wc = WordCloud(
                font_path = f'./static/fonts/{font}.ttf', 
                relative_scaling = 0.5,
                min_font_size = 1,
                background_color = bgcolor,
                width = int(request.form['width']),
                height = int(request.form['height']),
                max_words = int(request.form['maxword']),
                colormap = 'plasma', 
                scale = 1,
                mask = mask,
                #contour_width=3,
                #contour_color='indianred',
                stopwords = stopwords,
                mode='RGB',
                regexp = r'[ก-๙A-z0-9][ก-๙A-z0-9\.\-]*',
                font_step = 2,
                collocations=False,
                margin=20,).generate(tokens)
            print(time.time()-s)
            # if there are 10 files in tempfile, remove one
            tempfiles = sorted(glob.glob('static/tempfile/*'))
            if len(tempfiles) >= 10:
                os.remove(tempfiles[0])
                os.remove(tempfiles[1])
            # create random filename
            filename = 'wordcloud_' + time.strftime('%Y%m%d_%H%M%S')
            pngpath = f'static/tempfile/{filename}.png'
            svgpath = f'static/tempfile/{filename}.svg'
            wc.to_file(pngpath)
            with open(svgpath, 'w') as f:
                f.write(wc.to_svg())
            print(time.time()-s)
            return render_template('wordcloud.html', text=text, stopwords=request.form['stopwords'], pngpath=pngpath, svgpath=svgpath)
        except:
            return render_template('wordcloud.html')


################################################################################
#####   WORD2VEC
################################################################################

@app.route("/w2v", methods=['GET', 'POST'])
def page_w2v():
    if request.method == 'GET':
        return render_template('w2v.html', result=None)
    else:
        print(request.form)
        word1 = request.form['input_1'].strip()
        word2 = request.form['input_2'].strip()
        word3 = request.form['input_3'].strip()
        input_equation = word1
        pos = [word1]
        neg = []
        if word2 != '':
            input_equation += f' - {word2}'
            neg.append(word2)
        if word3 != '':
            input_equation += f' + {word3}'
            pos.append(word3)
        try:
            result = MODEL_THAIRATH.most_similar(positive=pos, negative=neg, topn=10)
            result = [(tpl[0], round(tpl[1],3)) for tpl in result]
        except:
            result = [['NOT FOUND', '']]
        return jsonify({'inputs':input_equation, 'result':result})



################################################################################
#####   SPLIT CHARACTER
################################################################################

@app.route("/split", methods=['GET', 'POST'])
def page_split():
    if request.method == 'GET':
        return render_template('split.html', result=None)
    else:
        text = request.form['text']
        new = ''
        for c in text:
            if re.match(r'[\u0e31\u0e33-\u0e3A\u0e47-\u0e4e]', c):
                new += c
            else:
                new += ' ' + c
        # ำ = \u0e33, tone = \u0e48-\u0e4b, ํ = \u0e4d
        new = re.sub(r'([\u0e01-\u0e2e])\u0e33([\u0e48-\u0e4b]?)', r'\1\2'+'\u0e4d า', new)
        new = re.sub(r'([\u0e01-\u0e2e])([\u0e48-\u0e4b]?)\u0e33', r'\1\2'+'\u0e4d า', new)
        return render_template('split.html', result=new.strip(), text=text)

################################################################################
#####   REGEX SIMULATIOR
################################################################################

# regex
@app.route('/regex', methods=['GET', 'POST'])
def regex_page():
    if request.method == 'GET':
        return render_template('regex.html')
    else:
        # Ajax
        try:
            string = list(request.form['string']) # list of character
            expr = request.form['expr']
            result = eval(expr.split('result = ', 1)[1])
            if request.form['mode'] in ['match', 'search']:
                if result:
                    # highlighted string
                    string.insert(result.span(0)[1], '</span>')
                    string.insert(result.span(0)[0], '<span class="bg_blue">')
                    # for capture: e.g. result.group(1)
                    index = 1
                    groups = []; spans = []
                    while True:
                        try:
                            groups.append(result.group(index))
                            spans.append(result.span(index))
                            index += 1
                        except:
                            break
                    return jsonify({'bool':True,
                        'group0': result.group(0),
                        'span0': result.span(0),
                        'groups': groups,
                        'spans': spans,
                        'string': ''.join(string)
                        })
                else:
                    return jsonify({'bool':False})
            elif request.form['mode'] in ['findall', 'split', 'sub']:
                pattern = request.form['pattern']
                string = re.sub(r'({})'.format(pattern), r'<span class="bg_blue">\1</span>', ''.join(string))
                return jsonify({'bool':bool(result), 'string':string, 'result':result})
        except:
            print("Unexpected error:", sys.exc_info()[0])
            return jsonify({'bool':'ERROR'})

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



###########################################################

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)