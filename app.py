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

print("Environment Variables:")
print(f"API_URL exists: {'API_URL' in os.environ}")
print(f"API_KEY exists: {'API_KEY' in os.environ}")
print(f"index_id exists: {'index_id' in os.environ}")


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

        api_url = "https://api.twelvelabs.io/v1.3/tasks" 
        print(f"Attempting to connect to API: {api_url}")
        print(f"API Key (first 4 chars): {API_KEY[:4]}...")
        
        response = requests.get(api_url, headers={
            "x-api-key": API_KEY,
            "Accept": "application/json"
        })
        print(f"Response status code: {response.status_code}")
        return response.status_code in [200, 401, 403]
    except requests.RequestException as e:
        print(f"API connection check failed. Detailed error: {str(e)}")
        return False
    



def process_api_response(data):
    processed_data = {
        "confidence": 0,
        "clarity": 0,
        "speech_rate": 0,
        "eye_contact": 0,
        "body_language": 0,
        "voice_tone": 0,
        "imp_points": []
    }
    
    try:
        if isinstance(data, str):

            try:
                import re
                json_match = re.search(r'\{[\s\S]*\}', data)
                if json_match:
                    data = json.loads(json_match.group())
                else:
                    data = json.loads(data)
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {e}")
                print(f"Raw data: {data}")
                return processed_data
        
        if isinstance(data, dict):
            for key in processed_data.keys():
                if key in data:
                    if isinstance(data[key], (int, float)):
                        processed_data[key] = data[key]
                    elif isinstance(data[key], str) and data[key].replace('.', '').isdigit():
                        processed_data[key] = float(data[key])
                    elif key == 'imp_points' and isinstance(data[key], list):
                        processed_data[key] = data[key]
                        
    except Exception as e:
        print(f"Error processing response: {e}")
        print(f"Raw data: {data}")
    
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
    
    file_size = os.path.getsize(video_path)
    if file_size > 2 * 1024 * 1024 * 1024:  
        return jsonify({"error": "Video file size exceeds 2GB limit"}), 400

    try:
        task = client.task.create(
            index_id=index_id,
            file=video_path
        )
        
        def on_task_update(task: Task):
            print(f"Task Status={task.status}")

        task.wait_for_done(sleep_interval=5, callback=on_task_update)
        
        if task.status != "ready":
            raise RuntimeError(f"Indexing failed with status {task.status}")

        print("Task completed successfully. Video ID:", task.video_id)
        
        prompt = """You're an Interviewer, Analyze the video clip of the interview answer. 
        If the face is not present in the video then provide lower points (less than 5) for all categories.

        Provide the response in the following JSON format with numerical values from 1-10:
        {
            "confidence": <number>,
            "clarity": <number>,
            "speech_rate": <number>,
            "eye_contact": <number>,
            "body_language": <number>,
            "voice_tone": <number>,
            "imp_points": [<list of important points as strings>]
        }"""

        result = client.generate.text(
            video_id=task.video_id,
            prompt=prompt
        )
 
        print("Raw API Response:", result.data)
        
        processed_data = process_api_response(result.data)
        return jsonify(processed_data), 200
        
    except Exception as e:
        print(f"Error processing video: {str(e)}")
        return jsonify({"error": f"Error processing video: {str(e)}"}), 500
    

if __name__ == '__main__':
    os.makedirs('uploads', exist_ok=True)
    app.run(debug=True)