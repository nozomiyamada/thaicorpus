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
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET, POST')
    return response


# web API https://thaicorpus.herokuapp.com/
# 0. pip freeze > requirements.txt
# 1. heroku login > heroku git:remote -a thaicorpus
# 2. git add -A  => git commit -m update 
# 3. git push heroku master
# 4. heroku logs --tail


################################################################################
#####   CORPUS PAGE
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
#####   G2P PAGE
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
#####   5. WORD2VEC PAGE
################################################################################

@app.route("/w2v", methods=['GET', 'POST'])
def page_w2v():
    if request.method == 'GET':
        return render_template('w2v.html')
    else: # Ajax
        word1 = request.form['input_1'].strip()
        word2 = request.form['input_2'].strip()
        word3 = request.form['input_3'].strip()
        input_equation = word1 # string : "word1 - word2 + word3"
        pos_words = [word1] 
        neg_words = []
        if word2 != '':
            input_equation += f' - {word2}'
            neg_words.append(word2)
        if word3 != '':
            input_equation += f' + {word3}'
            pos_words.append(word3)
        try:
            result = MODEL_THAIRATH.most_similar(positive=pos_words, negative=neg_words, topn=10)
            result = [(tpl[0], round(tpl[1],3)) for tpl in result]
        except:
            result = [['NOT FOUND', '']]
        return jsonify({'inputs':input_equation, 'result':result})


################################################################################
#####   6. SPLIT CHARACTER PAGE
################################################################################

@app.route("/split", methods=['GET', 'POST'])
def page_split():
    if request.method == 'GET':
        return render_template('split.html', result=None)
    else:
        text = request.form['input_text']
        new = ''
        for c in text:
            if re.match(r'[\u0e31\u0e33-\u0e3A\u0e47-\u0e4e]', c):
                new += c
            else:
                new += ' ' + c
        # ำ = \u0e33, tone = \u0e48-\u0e4b, ํ = \u0e4d
        new = re.sub(r'([\u0e01-\u0e2e])\u0e33([\u0e48-\u0e4b]?)', r'\1\2'+'\u0e4d า', new)
        new = re.sub(r'([\u0e01-\u0e2e])([\u0e48-\u0e4b]?)\u0e33', r'\1\2'+'\u0e4d า', new)
        return jsonify({'result':new.strip()})


################################################################################
#####   REGEX SIMULATIOR PAGE
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


###########################################################

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)