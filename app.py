from flask import Flask, render_template, request, jsonify, session, send_file
import torch
from transformers import GPT2LMHeadModel, GPT2Tokenizer, pipeline
import os
import re
import logging
import json
import uuid
from datetime import datetime
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
import textwrap

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Initialize database
def init_db():
    """Initialize the SQLite database"""
    conn = sqlite3.connect('stories.db')
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
        self.model = None
        self.tokenizer = None
        self.generator = None
        self.model_name = "gpt2-medium"
        self.models_dir = "./models"  # Local models directory
        self.local_model_path = os.path.join(self.models_dir, "gpt2_medium")
        
        self.genres = {
            'fantasy': "In a magical realm where",
            'sci-fi': "In the distant future where technology has advanced beyond imagination,",
            'mystery': "The fog rolled in that evening, and with it came secrets that would",
            'romance': "Their eyes met across the crowded room, and in that moment",
            'horror': "The old house stood at the end of the street, its windows dark and",
            'adventure': "The map was old and weathered, but it promised treasures beyond",
            'comedy': "It was supposed to be a normal Tuesday, but nothing about this day would be"
        }
        self.load_model()
    
    def ensure_model_directory(self):
        """Create models directory if it doesn't exist"""
        os.makedirs(self.models_dir, exist_ok=True)
        os.makedirs(self.local_model_path, exist_ok=True)
    
    def download_and_save_model(self):
        """Download model and save it locally"""
        logger.info(f"Downloading {self.model_name} to {self.local_model_path}")
        
        try:
            # Download from Hugging Face
            tokenizer = GPT2Tokenizer.from_pretrained(self.model_name)
            model = GPT2LMHeadModel.from_pretrained(self.model_name)
            
            # Save to local directory
            tokenizer.save_pretrained(self.local_model_path)
            model.save_pretrained(self.local_model_path)
            
            logger.info(f"Model saved successfully to {self.local_model_path}")
            return model, tokenizer
            
        except Exception as e:
            logger.error(f"Error downloading model: {str(e)}")
            raise e
    
    def load_model(self):
        """Load the AI model and tokenizer"""
        try:
            self.ensure_model_directory()
            
            # Check if model exists locally
            config_path = os.path.join(self.local_model_path, "config.json")
            
            if os.path.exists(config_path):
                # Load from local directory
                logger.info(f"Loading model from local directory: {self.local_model_path}")
                self.tokenizer = GPT2Tokenizer.from_pretrained(self.local_model_path)
                self.model = GPT2LMHeadModel.from_pretrained(self.local_model_path)
            else:
                # Download and save locally
                logger.info(f"Model not found locally. Downloading {self.model_name}...")
                self.model, self.tokenizer = self.download_and_save_model()
            
            self.tokenizer.pad_token = self.tokenizer.eos_token
            
            self.generator = pipeline(
                'text-generation',
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if torch.cuda.is_available() else -1
            )
            
            logger.info("Model loaded successfully!")
            logger.info(f"Model location: {os.path.abspath(self.local_model_path)}")
            
        except Exception as e:
            logger.error(f"Error loading model: {str(e)}")
            raise e
    
    def get_model_info(self):
        """Get information about the loaded model"""
        return {
            'model_name': self.model_name,
            'local_path': os.path.abspath(self.local_model_path),
            'model_exists': os.path.exists(os.path.join(self.local_model_path, "config.json")),
            'model_size_mb': self.get_model_size()
        }
    
    def get_model_size(self):
        """Calculate model size in MB"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(self.local_model_path):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
            return round(total_size / (1024 * 1024), 2)  # Convert to MB
        except:
            return 0
    
    def generate_story(self, prompt, max_length=300, temperature=0.8, top_p=0.9, genre=None):
        """Generate a story based on the given prompt"""
        try:
            # Add genre-specific prefix if specified
            if genre and genre in self.genres:
                genre_prompt = self.genres[genre]
                prompt = f"{genre_prompt} {prompt}"
            
            cleaned_prompt = self.clean_prompt(prompt)
            
            generated = self.generator(
                cleaned_prompt,
                max_length=max_length,
                temperature=temperature,
                top_p=top_p,
                top_k=50,
                do_sample=True,
                num_return_sequences=1,
                pad_token_id=self.tokenizer.eos_token_id,
                truncation=True
            )
            
            story = generated[0]['generated_text']
            story = self.post_process_story(story, cleaned_prompt)
            
            return story
            
        except Exception as e:
            logger.error(f"Error generating story: {str(e)}")
            return f"Sorry, there was an error generating your story: {str(e)}"
    
    def generate_multiple_endings(self, story_beginning, num_endings=3):
        """Generate multiple different endings for a story"""
        endings = []
        for i in range(num_endings):
            # Use different temperature values for variety
            temp = 0.7 + (i * 0.1)
            ending = self.generate_story(
                story_beginning + " The story concluded when",
                max_length=150,
                temperature=temp
            )
            endings.append(ending)
        return endings
    
    def enhance_story(self, story, enhancement_type="detail"):
        """Enhance an existing story with more details, dialogue, or descriptions"""
        enhancement_prompts = {
            "detail": "Expand this story with more vivid details and descriptions: ",
            "dialogue": "Rewrite this story adding more character dialogue: ",
            "emotion": "Rewrite this story emphasizing the emotions and feelings: ",
            "action": "Rewrite this story with more action and excitement: "
        }
        
        prompt = enhancement_prompts.get(enhancement_type, enhancement_prompts["detail"])
        enhanced = self.generate_story(prompt + story, max_length=len(story.split()) * 2)
        return enhanced
    
    def clean_prompt(self, prompt):
        """Clean and format the input prompt"""
        prompt = prompt.strip()
        if not prompt.endswith('.') and not prompt.endswith('!') and not prompt.endswith('?'):
            prompt += '.'
        return prompt
    
    def post_process_story(self, story, original_prompt):
        """Clean up the generated story"""
        if story.startswith(original_prompt):
            story = story[len(original_prompt):].strip()
        
        story = re.sub(r'\n+', '\n\n', story)
        story = re.sub(r'\s+', ' ', story)
        
        if not story.startswith(original_prompt):
            story = original_prompt + ' ' + story
        
        return story.strip()

# Database helper functions
def get_db():
    """Get database connection"""
    conn = sqlite3.connect('stories.db')
    conn.row_factory = sqlite3.Row
    return conn

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
    conn.close()
    return story_id

def get_user_stories(user_id):
    """Get all stories for a user"""
    conn = get_db()
    stories = conn.execute('''
        SELECT * FROM stories WHERE user_id = ? ORDER BY created_at DESC
    ''', (user_id,)).fetchall()
    conn.close()
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
    conn.close()
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
        
        if not prompt:
            return jsonify({'error': 'Please provide a story prompt'}), 400
        
        # Get generation parameters
        max_length = min(int(data.get('max_length', 300)), 1000)
        temperature = float(data.get('temperature', 0.8))
        top_p = float(data.get('top_p', 0.9))
        genre = data.get('genre')
        
        # Generate the story
        story = story_gen.generate_story(
            prompt=prompt,
            max_length=max_length,
            temperature=temperature,
            top_p=top_p,
            genre=genre
        )
        
        # Save story if user is logged in
        if 'user_id' in session:
            story_data = {
                'title': data.get('title', 'Generated Story'),
                'prompt': prompt,
                'story': story,
                'genre': genre,
                'is_public': data.get('is_public', False)
            }
            story_id = save_story(session['user_id'], story_data)
        else:
            story_id = None
        
        return jsonify({
            'story': story,
            'prompt': prompt,
            'story_id': story_id,
            'word_count': len(story.split()),
            'genre': genre
        })
        
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
        conn.close()
        
        if not story:
            return jsonify({'error': 'Story not found'}), 404
        
        # Create PDF
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        styles = getSampleStyleSheet()
        story_elements = []
        
        # Title
        title = Paragraph(f"<b>{story['title']}</b>", styles['Title'])
        story_elements.append(title)
        story_elements.append(Spacer(1, 12))
        
        # Story content
        story_text = story['story']
        paragraphs = story_text.split('\n\n')
        
        for para in paragraphs:
            if para.strip():
                p = Paragraph(para, styles['Normal'])
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
        conn.close()
        
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
        conn.close()
        
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
    
    conn.close()
    
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