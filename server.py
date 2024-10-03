import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from nltk.corpus import stopwords
from urllib.parse import parse_qs, urlparse
import json
import pandas as pd
from datetime import datetime
import uuid
import os
from typing import Callable, Any
from wsgiref.simple_server import make_server

nltk.download('vader_lexicon', quiet=True)
nltk.download('punkt', quiet=True)
nltk.download('averaged_perceptron_tagger', quiet=True)
nltk.download('stopwords', quiet=True)

adj_noun_pairs_count = {}
sia = SentimentIntensityAnalyzer()
stop_words = set(stopwords.words('english'))

reviews = pd.read_csv('data/reviews.csv').to_dict('records')

valid_locations = {
    "Albuquerque, New Mexico", "Carlsbad, California", "Chula Vista, California",
    "Colorado Springs, Colorado", "Denver, Colorado", "El Cajon, California",
    "El Paso, Texas", "Escondido, California", "Fresno, California", "La Mesa, California",
    "Las Vegas, Nevada", "Los Angeles, California", "Oceanside, California",
    "Phoenix, Arizona", "Sacramento, California", "Salt Lake City, Utah",
    "San Diego, California", "Tucson, Arizona"
}

class ReviewAnalyzerServer:
    def __init__(self) -> None:
        # This method is a placeholder for future initialization logic
        pass
    
     # checking dates
    def within_date(self, timestamp_str, s_date_str, e_date_str):
        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
        start_date = datetime.strptime(
            s_date_str, '%Y-%m-%d') if s_date_str else datetime.min
        end_date = datetime.strptime(
            e_date_str, '%Y-%m-%d') if e_date_str else datetime.max
        return start_date <= timestamp <= end_date

    def analyze_sentiment(self, review_body):
        sentiment_scores = sia.polarity_scores(review_body)
        return sentiment_scores

    def __call__(self, environ: dict[str, Any], start_response: Callable[..., Any]) -> bytes:
        """
        The environ parameter is a dictionary containing some useful
        HTTP request information such as: REQUEST_METHOD, CONTENT_LENGTH, QUERY_STRING,
        PATH_INFO, CONTENT_TYPE, etc.
        """

        if environ["REQUEST_METHOD"] == "GET":
            # get query string from req
            query_str = parse_qs(environ['QUERY_STRING'])
            location = query_str.get('location', [None])[0]
            start_date = query_str.get('start_date', [None])[0]
            end_date = query_str.get('end_date', [None])[0]

            # get all review data
            f_reviews = reviews

            # Filter by location
            if location:
                if location not in valid_locations:
                    start_response("400 Bad Request", [
                                   ("Content-Type", "application/json")])
                    return [b"Not Valid location"]
                f_reviews = [
                    review for review in f_reviews if review['Location'] == location]

            # date filter
            if start_date or end_date:
                f_reviews = [review for review in f_reviews if self.within_date(
                    review['Timestamp'], start_date, end_date)]

            # sentiment add
            for review in f_reviews:
                review['sentiment'] = self.analyze_sentiment(
                    review['ReviewBody'])

            # sort review
            sort_reviews = sorted(
                f_reviews, key=lambda x: x['sentiment']['compound'], reverse=True)

            # Create the response body from the reviews and convert to a JSON byte string
            response_body = json.dumps(
                sort_reviews, indent=2).encode("utf-8")

            # Set the appropriate response headers
            start_response("200 OK", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(response_body)))
            ])

            return [response_body]


        if environ["REQUEST_METHOD"] == "POST":
            # check body size
            try:
                req_body_size = int(environ.get('CONTENT_LENGTH', 0))
            except ValueError:
                req_body_size = 0

            # read input
            request_body = environ['wsgi.input'].read(
                req_body_size).decode('utf-8')
            review_data = parse_qs(request_body)

            # validate body
            if 'ReviewBody' not in review_data or 'Location' not in review_data:
                start_response("400 Bad Request", [
                               ("Content-Type", "text/plain")])
                return [b"Missing ReviewBody or Location parameter"]

            # check valid Location
            location = review_data['Location'][0]
            if location not in valid_locations:
                start_response("400 Bad Request", [
                               ("Content-Type", "text/plain")])
                return [b"Invalid Location parameter"]

            # Create a new review
            create_review = {
                'ReviewId': str(uuid.uuid4()),
                'ReviewBody': review_data['ReviewBody'][0],
                'Location': review_data['Location'][0],
                'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            reviews.append(create_review)

            response_body = json.dumps(create_review, indent=2).encode("utf-8")
            start_response("201 Created", [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(response_body)))
            ])
            return [response_body]


   

if __name__ == "__main__":
    app = ReviewAnalyzerServer()
    port = os.environ.get('PORT', 8000)
    with make_server("", port, app) as httpd:
        print(f"Listening on port {port}...")
        httpd.serve_forever()