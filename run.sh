cp words_th.txt venv/lib/python3.9/site-packages/pythainlp/corpus/words_th.txt
source venv/bin/activate
gunicorn --daemon app:app --bind=0.0.0.0:8000