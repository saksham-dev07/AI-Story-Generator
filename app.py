from flask import Flask, render_template, request, jsonify, session, send_file, g
import requests
from google import genai
import os
import re
import logging
from dotenv import load_dotenv

load_dotenv()
import json
import uuid
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask import Response
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
import textwrap
from xml.sax.saxutils import escape

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Initialize database
def init_db():
    """Initialize the SQLite database"""
    with sqlite3.connect('stories.db') as conn:
        c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Stories table
    c.execute('''
        CREATE TABLE IF NOT EXISTS stories (
            id TEXT PRIMARY KEY,
            user_id INTEGER,
            title TEXT,
            prompt TEXT NOT NULL,
            story TEXT NOT NULL,
            genre TEXT,
            word_count INTEGER,
            rating INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_public BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Story collections/favorites
    c.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            story_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (story_id) REFERENCES stories (id)
        )
    ''')
    
    conn.commit()
    conn.close()

class StoryGenerator:
    def __init__(self):
        self.model_name = "gemini-3.1-flash-lite"
        
        # Configure Gemini API
        api_key = os.environ.get("GEMINI_API_KEY")
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            logger.warning("GEMINI_API_KEY environment variable not set!")
            self.client = None
            
        self.genres = {
            'fantasy': "In a magical realm where",
            'sci-fi': "In the distant future where technology has advanced beyond imagination,",
            'mystery': "The fog rolled in that evening, and with it came secrets that would",
            'romance': "Their eyes met across the crowded room, and in that moment",
            'horror': "The old house stood at the end of the street, its windows dark and",
            'adventure': "The map was old and weathered, but it promised treasures beyond",
            'comedy': "It was supposed to be a normal Tuesday, but nothing about this day would be"
        }
    
    def get_model_info(self):
        """Get information about the loaded model"""
        return {
            'model_name': self.model_name,
            'local_path': "Google Cloud API",
            'model_exists': bool(os.environ.get("GEMINI_API_KEY")),
            'model_size_mb': "Cloud"
        }
    
    def get_model_size(self):
        return 0
    
    def _call_gemini(self, prompt, temperature, top_p):
        """Helper to call Gemini API"""
        if not os.environ.get("GEMINI_API_KEY") or not self.client:
            raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it to use the AI generator.")
            
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=temperature,
                    top_p=top_p,
                )
            )
            return response.text
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "exhausted" in error_msg.lower():
                logger.error(f"Rate limit hit: {error_msg}")
                raise Exception("RATE_LIMIT")
            logger.error(f"Gemini API error: {error_msg}")
            raise e
            
    def _call_gemini_stream(self, prompt, temperature, top_p):
        """Helper to call Gemini API and stream the response"""
        if not os.environ.get("GEMINI_API_KEY") or not self.client:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")
            
        try:
            response = self.client.models.generate_content_stream(
                model=self.model_name,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    temperature=temperature,
                    top_p=top_p,
                )
            )
            for chunk in response:
                yield chunk.text
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "quota" in error_msg.lower() or "exhausted" in error_msg.lower():
                logger.error(f"Rate limit hit: {error_msg}")
                raise Exception("RATE_LIMIT")
            logger.error(f"Gemini API error: {error_msg}")
            raise e
            
    def generate_story(self, prompt, max_length=300, temperature=0.8, top_p=0.9, genre=None):
        """Generate a story based on the given prompt"""
        try:
            if genre and genre in self.genres:
                genre_prompt = self.genres[genre]
                prompt = f"{genre_prompt} {prompt}"
            
            prompt = self.clean_prompt(prompt)
            instruct_prompt = f"Write a creative story starting exactly with the following prompt. Do not include any meta-commentary, titles, or intro, just write the story. Make the story roughly {max_length} words.\n\nPrompt: {prompt}"
            
            story_text = self._call_gemini(instruct_prompt, temperature, top_p)
            
            return self.post_process_story(story_text, prompt)
            
        except Exception as e:
            if str(e) == "RATE_LIMIT":
                return "⏳ You are generating stories too fast! Google's Free Tier limits you to 5 requests per minute. Please wait about 60 seconds and try again."
            logger.error(f"Error generating story: {str(e)}")
            return f"Sorry, there was an error generating your story. Did you set your GEMINI_API_KEY? Error: {str(e)}"
    
    def generate_multiple_endings(self, story_beginning, num_endings=3):
        """Generate multiple different endings for a story"""
        endings = []
        for i in range(num_endings):
            temp = 0.7 + (i * 0.1)
            prompt = f"Provide a single possible short ending for the following story. Do not provide commentary, just the ending text.\n\nStory: {story_beginning}"
            ending = self._call_gemini(prompt, temp, 0.9)
            endings.append(ending)
        return endings
    
    def enhance_story(self, story, enhancement_type="detail"):
        """Enhance an existing story with more details, dialogue, or descriptions"""
        enhancement_prompts = {
            "detail": "Rewrite and expand this story with more vivid details and descriptions:\n\n",
            "dialogue": "Rewrite this story adding more character dialogue:\n\n",
            "emotion": "Rewrite this story emphasizing the emotions and feelings of the characters:\n\n",
            "action": "Rewrite this story with more action and excitement:\n\n"
        }
        
        instruction = enhancement_prompts.get(enhancement_type, enhancement_prompts["detail"])
        prompt = f"{instruction}{story}\n\nJust provide the rewritten story without any introductory text."
        
        enhanced = self._call_gemini(prompt, 0.7, 0.9)
        return enhanced
    
    def clean_prompt(self, prompt):
        """Clean and format the input prompt"""
        prompt = prompt.strip()
        if not prompt.endswith('.') and not prompt.endswith('!') and not prompt.endswith('?'):
            prompt += '.'
        return prompt
    
    def post_process_story(self, story, original_prompt):
        """Clean up the generated story"""
        story = re.sub(r'\n+', '\n\n', story).strip()
        
        if original_prompt.lower() not in story[:200].lower():
            story = original_prompt + ' ' + story
            
        return story
        
        return story.strip()

# Database helper functions
def get_db():
    """Get database connection"""
    if 'db' not in g:
        g.db = sqlite3.connect('stories.db')
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        db.close()

def save_story(user_id, story_data):
    """Save a story to the database"""
    conn = get_db()
    story_id = str(uuid.uuid4())
    
    conn.execute('''
        INSERT INTO stories (id, user_id, title, prompt, story, genre, word_count, is_public)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        story_id,
        user_id,
        story_data.get('title', 'Untitled Story'),
        story_data['prompt'],
        story_data['story'],
        story_data.get('genre'),
        len(story_data['story'].split()),
        story_data.get('is_public', False)
    ))
    
    conn.commit()
    return story_id

def get_user_stories(user_id):
    """Get all stories for a user"""
    conn = get_db()
    stories = conn.execute('''
        SELECT * FROM stories WHERE user_id = ? ORDER BY created_at DESC
    ''', (user_id,)).fetchall()
    return [dict(story) for story in stories]

def get_public_stories(limit=20):
    """Get public stories"""
    conn = get_db()
    stories = conn.execute('''
        SELECT s.*, u.username FROM stories s
        JOIN users u ON s.user_id = u.id
        WHERE s.is_public = 1
        ORDER BY s.created_at DESC
        LIMIT ?
    ''', (limit,)).fetchall()
    return [dict(story) for story in stories]

# Initialize the story generator and database
story_gen = StoryGenerator()
init_db()

@app.route('/')
def index():
    """Main page"""
    return render_template('index.html')

@app.route('/model-info')
def model_info():
    """Get model information"""
    return jsonify(story_gen.get_model_info())

@app.route('/generate', methods=['POST'])
def generate():
    """Generate story endpoint"""
    try:
        data = request.get_json()
        prompt = data.get('prompt', '')
        
        char_name = data.get('character_name', '').strip()
        char_traits = data.get('character_traits', '').strip()
        
        if char_name or char_traits:
            char_info = f"The main character is {char_name if char_name else 'someone'}."
            if char_traits:
                char_info += f" They are {char_traits}."
            prompt = f"{char_info} {prompt}"
            
        
        if not prompt:
            return jsonify({'error': 'Please provide a story prompt'}), 400
        
        # Get generation parameters
        max_length = min(int(data.get('max_length', 300)), 1000)
        temperature = float(data.get('temperature', 0.8))
        top_p = float(data.get('top_p', 0.9))
        genre = data.get('genre')
                # Extract variables before starting stream generator
        user_id = session.get('user_id')
        story_title = data.get('title', 'Generated Story')
        is_public = data.get('is_public', False)
        
        # Pollinations.ai image URL
        import urllib.parse
        encoded_prompt = urllib.parse.quote(prompt[:200])
        image_url = f"https://image.pollinations.ai/prompt/{encoded_prompt}?width=1024&height=512&nologo=true"
        
        def generate_stream():
            try:
                # Send initial setup with cover image
                yield f"data: {json.dumps({'type': 'init', 'image': image_url})}\n\n"
                
                final_prompt = prompt
                if genre and genre in story_gen.genres:
                    final_prompt = f"{story_gen.genres[genre]} {final_prompt}"
                
                final_prompt = story_gen.clean_prompt(final_prompt)
                instruct_prompt = f"Write a creative story starting exactly with the following prompt. You MUST use Markdown formatting (like **bold**, *italics*, and headers) to make the story visually engaging. Do not include any meta-commentary, titles, or intro, just write the story. Make the story roughly {max_length} words.\n\nPrompt: {final_prompt}"
                
                full_story = ""
                for chunk in story_gen._call_gemini_stream(instruct_prompt, temperature, top_p):
                    if chunk:
                        full_story += chunk
                        yield f"data: {json.dumps({'type': 'chunk', 'text': chunk})}\n\n"
                
                # Save story if user is logged in
                story_id = None
                if user_id:
                    story_data = {
                        'title': story_title,
                        'prompt': prompt,
                        'story': full_story,
                        'genre': genre,
                        'is_public': is_public
                    }
                    story_id = save_story(user_id, story_data)
                
                word_count = len(full_story.split())
                yield f"data: {json.dumps({'type': 'done', 'story_id': story_id, 'word_count': word_count})}\n\n"
                
            except Exception as e:
                if str(e) == "RATE_LIMIT":
                    err = "⏳ You are generating stories too fast! Google's Free Tier limits you to 15 requests per minute. Please wait about 60 seconds and try again."
                else:
                    err = f"Error generating story: {str(e)}"
                yield f"data: {json.dumps({'type': 'error', 'error': err})}\n\n"

        return Response(generate_stream(), mimetype='text/event-stream')
        
    except Exception as e:
        logger.error(f"Error in generate endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/enhance', methods=['POST'])
def enhance():
    """Enhance an existing story"""
    try:
        data = request.get_json()
        story = data.get('story', '')
        enhancement_type = data.get('type', 'detail')
        
        if not story:
            return jsonify({'error': 'Please provide a story to enhance'}), 400
        
        enhanced_story = story_gen.enhance_story(story, enhancement_type)
        
        return jsonify({
            'enhanced_story': enhanced_story,
            'enhancement_type': enhancement_type,
            'word_count': len(enhanced_story.split())
        })
        
    except Exception as e:
        logger.error(f"Error in enhance endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/multiple-endings', methods=['POST'])
def multiple_endings():
    """Generate multiple endings for a story"""
    try:
        data = request.get_json()
        story_beginning = data.get('story', '')
        num_endings = min(int(data.get('num_endings', 3)), 5)
        
        if not story_beginning:
            return jsonify({'error': 'Please provide a story beginning'}), 400
        
        endings = story_gen.generate_multiple_endings(story_beginning, num_endings)
        
        return jsonify({
            'endings': endings,
            'num_endings': len(endings)
        })
        
    except Exception as e:
        logger.error(f"Error in multiple-endings endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/random-prompt')
def random_prompt():
    """Generate a random story prompt"""
    prompts = [
        "A mysterious letter arrives at your door with no return address",
        "You wake up with the ability to hear everyone's thoughts",
        "The last person on Earth discovers they're not alone",
        "A time traveler gets stuck in the wrong century",
        "Your reflection starts acting independently",
        "You find a door in your basement that wasn't there yesterday",
        "The world's colors start disappearing one by one",
        "You inherit a house with rooms that change every night",
        "A stranger approaches you claiming to be your future self",
        "You discover your dreams are someone else's memories"
    ]
    
    import random
    return jsonify({'prompt': random.choice(prompts)})

@app.route('/export-pdf/<story_id>')
def export_pdf(story_id):
    """Export a story as PDF"""
    try:
        conn = get_db()
        story = conn.execute('SELECT * FROM stories WHERE id = ?', (story_id,)).fetchone()
        
        if not story:
            return jsonify({'error': 'Story not found'}), 404
            
        if not story['is_public'] and story['user_id'] != session.get('user_id'):
            return jsonify({'error': 'Unauthorized to access this story'}), 403
        
        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story_elements = []
        
        # Title
        safe_title = escape(story['title'])
        title = Paragraph(f"<b>{safe_title}</b>", styles['Title'])
        story_elements.append(title)
        story_elements.append(Spacer(1, 12))
        
        # Story content
        story_text = story['story']
        paragraphs = story_text.split('\n\n')
        
        for para in paragraphs:
            if para.strip():
                safe_para = escape(para)
                p = Paragraph(safe_para, styles['Normal'])
                story_elements.append(p)
                story_elements.append(Spacer(1, 6))
        
        doc.build(story_elements)
        buffer.seek(0)
        
        return send_file(
            io.BytesIO(buffer.read()),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{story['title']}.pdf"
        )
        
    except Exception as e:
        logger.error(f"Error exporting PDF: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/my-stories')
def my_stories():
    """Get user's stories"""
    if 'user_id' not in session:
        return jsonify({'error': 'Please log in'}), 401
    
    stories = get_user_stories(session['user_id'])
    return jsonify({'stories': stories})

@app.route('/public-stories')
def public_stories():
    """Get public stories"""
    stories = get_public_stories()
    return jsonify({'stories': stories})

@app.route('/continue', methods=['POST'])
def continue_story():
    """Continue story endpoint"""
    try:
        data = request.get_json()
        story_text = data.get('story', '')
        
        if not story_text:
            return jsonify({'error': 'Please provide a story to continue'}), 400
            
        temperature = float(data.get('temperature', 0.8))
        prompt = story_text[-500:] if len(story_text) > 500 else story_text
        
        continuation = story_gen.generate_story(
            prompt=prompt,
            max_length=min(len(prompt.split()) + 150, 1000),
            temperature=temperature
        )
        
        if continuation.startswith(prompt):
            continuation = continuation[len(prompt):].strip()
            
        return jsonify({'continuation': continuation})
        
    except Exception as e:
        logger.error(f"Error in continue endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/favorite/<story_id>', methods=['POST'])
def toggle_favorite(story_id):
    """Toggle a story as favorite"""
    if 'user_id' not in session:
        return jsonify({'error': 'Please log in'}), 401
        
    try:
        conn = get_db()
        existing = conn.execute(
            'SELECT id FROM favorites WHERE user_id = ? AND story_id = ?',
            (session['user_id'], story_id)
        ).fetchone()
        
        if existing:
            conn.execute('DELETE FROM favorites WHERE id = ?', (existing['id'],))
            is_favorite = False
        else:
            conn.execute(
                'INSERT INTO favorites (user_id, story_id) VALUES (?, ?)',
                (session['user_id'], story_id)
            )
            is_favorite = True
            
        conn.commit()
        return jsonify({'is_favorite': is_favorite})
        
    except Exception as e:
        logger.error(f"Error toggling favorite: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/favorites')
def get_favorites():
    """Get user's favorite stories"""
    if 'user_id' not in session:
        return jsonify({'error': 'Please log in'}), 401
        
    try:
        conn = get_db()
        stories = conn.execute('''
            SELECT s.*, u.username FROM favorites f
            JOIN stories s ON f.story_id = s.id
            JOIN users u ON s.user_id = u.id
            WHERE f.user_id = ?
            ORDER BY f.created_at DESC
        ''', (session['user_id'],)).fetchall()
        
        return jsonify({'stories': [dict(story) for story in stories]})
        
    except Exception as e:
        logger.error(f"Error getting favorites: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/register', methods=['POST'])
def register():
    """User registration"""
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        
        if not all([username, email, password]):
            return jsonify({'error': 'All fields are required'}), 400
        
        conn = get_db()
        
        # Check if user exists
        existing = conn.execute(
            'SELECT id FROM users WHERE username = ? OR email = ?',
            (username, email)
        ).fetchone()
        
        if existing:
            return jsonify({'error': 'Username or email already exists'}), 400
        
        # Create user
        password_hash = generate_password_hash(password)
        cursor = conn.execute(
            'INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)',
            (username, email, password_hash)
        )
        
        user_id = cursor.lastrowid
        conn.commit()
        
        session['user_id'] = user_id
        session['username'] = username
        
        return jsonify({'message': 'Registration successful', 'username': username})
        
    except Exception as e:
        logger.error(f"Error in register endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        
        if not all([username, password]):
            return jsonify({'error': 'Username and password are required'}), 400
        
        conn = get_db()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?',
            (username,)
        ).fetchone()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return jsonify({'message': 'Login successful', 'username': user['username']})
        else:
            return jsonify({'error': 'Invalid credentials'}), 401
            
    except Exception as e:
        logger.error(f"Error in login endpoint: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/logout', methods=['POST'])
def logout():
    """User logout"""
    session.clear()
    return jsonify({'message': 'Logged out successfully'})

@app.route('/story-stats')
def story_stats():
    """Get story statistics"""
    if 'user_id' not in session:
        return jsonify({'error': 'Please log in'}), 401
    
    conn = get_db()
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_stories,
            SUM(word_count) as total_words,
            AVG(word_count) as avg_words,
            genre,
            COUNT(*) as genre_count
        FROM stories 
        WHERE user_id = ?
        GROUP BY genre
    ''', (session['user_id'],)).fetchall()
    
    total_stats = conn.execute('''
        SELECT 
            COUNT(*) as total_stories,
            SUM(word_count) as total_words,
            AVG(word_count) as avg_words
        FROM stories 
        WHERE user_id = ?
    ''', (session['user_id'],)).fetchone()
    
    return jsonify({
        'total_stats': dict(total_stats) if total_stats else {},
        'genre_stats': [dict(stat) for stat in stats]
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy', 
        'model_loaded': story_gen.model is not None,
        'database_connected': True,
        'model_info': story_gen.get_model_info()
    })

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)