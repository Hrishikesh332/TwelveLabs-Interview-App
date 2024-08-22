import os
import json
import random
from flask import Flask, render_template, request, jsonify
from twelvelabs import TwelveLabs
from twelvelabs.models.task import Task
import requests
from dotenv import load_dotenv

load_dotenv()


app = Flask(__name__)

API_KEY = os.getenv('API_KEY')
API_URL = os.getenv('API_URL')
index_id = os.getenv('index_id')

client = TwelveLabs(api_key=API_KEY)

INTERVIEW_QUESTIONS = [
    "Tell me about yourself.",
    "What are your greatest strengths?",
    "What do you consider to be your weaknesses?",
    "Where do you see yourself in five years?",
    "Why should we hire you?",
    "What motivates you?",
    "What are your career goals?",
    "How do you work in a team?",
    "What's your leadership style?"
]

def check_api_connection():
    try:
        response = requests.get(API_URL, headers={"x-api-key": API_KEY})
        return response.status_code == 200
    except requests.RequestException as e:
        print(f"API connection check failed. Error: {str(e)}")
        return False

def process_api_response(data):
    processed_data = {
        "confidence": "N/A",
        "clarity": "N/A",
        "speech_rate": "N/A",
        "eye_contact": "N/A",
        "body_language": "N/A",
        "voice_tone": "N/A",
        "imp_points": []
    }
    if isinstance(data, str):
        try:
            cleaned_data = data.replace("```json", "").replace("```", "").strip()
            data = json.loads(cleaned_data)
        except json.JSONDecodeError as e:
            print(f"Error decoding JSON - {e}")
            return processed_data
    if isinstance(data, dict):
        for key in processed_data.keys():
            processed_data[key] = data.get(key, "N/A")
    return processed_data

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_question')
def get_question():
    question = random.choice(INTERVIEW_QUESTIONS)
    return jsonify({"question": question})

@app.route('/upload', methods=['POST'])
def upload():
    if not check_api_connection():
        return jsonify({"error": "Failed to connect to the Twelve Labs API."}), 500
    if 'video' not in request.files:
        return jsonify({"error": "No video file provided"}), 400
    video = request.files['video']
    if video.filename == '':
        return jsonify({"error": "No video file selected"}), 400

    video_path = os.path.join('uploads', 'interview.mp4')
    video.save(video_path)
    
    if not os.path.exists(video_path):
        return jsonify({"error": "Failed to save video file"}), 500

    file_size = os.path.getsize(video_path)
    print(f"Uploaded video file size: {file_size} bytes")

    if file_size == 0:
        return jsonify({"error": "Uploaded video file is empty"}), 500

    try:
        task = client.task.create(index_id=index_id, file=video_path)
        task.wait_for_done(sleep_interval=5)
        if task.status != "ready":
            return jsonify({"error": f"Indexing failed with status {task.status}"}), 500
        
        result = client.generate.text(
            video_id=task.video_id,
            prompt="""You're an Interviewer, Analyze the video clip of the interview answer for the question - {question}.
            If the face is not present in the video then do provide the lower points in all categories, Do provide less than 5 for all the other categories if the face is not visible in the video.

            Do provide the response in the json format with the number assigned as the value. 
            after analyzing from 1-10. The keys of the json as confidence, clarity, speech_rate, eye_contact, body_language, voice_tone, relevant_to_question, imp_points.
            The imp_points will contain the exact sentence in a summarized points by the speaker, also do remove the filler words and provide it in a list format which is important from video."""
        )
        
        print("Raw API Response:", json.dumps(result.data, indent=2))
        processed_data = process_api_response(result.data)
        print("Processed data:", json.dumps(processed_data, indent=2))
        return jsonify(processed_data), 200
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        return jsonify({"error": f"Error processing video: {str(e)}"}), 500

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True)