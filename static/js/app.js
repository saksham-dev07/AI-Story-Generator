let currentUser = null;
let currentStoryId = null;
let generatedStory = '';

// Authentication functions
async function login() {
    const username = document.getElementById('authUsername').value;
    const password = document.getElementById('authPassword').value;

    if (!username || !password) {
        if (!username) markInputError('authUsername');
        if (!password) markInputError('authPassword');
        showMessage('Please enter username and password', 'error');
        return;
    }

    try {
        const response = await fetch('/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (response.ok) {
            currentUser = data.username;
            
            // Force hide login elements
            document.getElementById('authForms').style.display = 'none';
            document.getElementById('registerForm').style.display = 'none';
            
            // Force show user info
            document.getElementById('userInfo').style.display = 'block';
            document.getElementById('loggedInActions').style.display = 'block';
            document.getElementById('username').textContent = currentUser;
            
            // Clear input fields
            document.getElementById('authUsername').value = '';
            document.getElementById('authPassword').value = '';
            
            showMessage('Login successful!', 'success');
            loadMyStories();
            loadStats();
        } else {
            showMessage(data.error, 'error');
        }
    } catch (error) {
        showMessage('Login failed', 'error');
    }
}

function showRegister() {
    document.getElementById('authForms').style.display = 'none';
    document.getElementById('registerForm').style.display = 'flex';
}

function hideRegister() {
    document.getElementById('authForms').style.display = 'flex';
    document.getElementById('registerForm').style.display = 'none';
}

async function register() {
    const username = document.getElementById('regUsername').value;
    const email = document.getElementById('regEmail').value;
    const password = document.getElementById('regPassword').value;

    if (!username || !email || !password) {
        if (!username) markInputError('regUsername');
        if (!email) markInputError('regEmail');
        if (!password) markInputError('regPassword');
        showMessage('Please fill all fields', 'error');
        return;
    }

    try {
        const response = await fetch('/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, email, password })
        });

        const data = await response.json();

        if (response.ok) {
            // Clear registration form fields
            document.getElementById('regUsername').value = '';
            document.getElementById('regEmail').value = '';
            document.getElementById('regPassword').value = '';
            
            // Hide register form and show login form
            hideRegister();
            
            // Show success message
            showMessage('Registration successful! Please login to continue.', 'success');
            
            // Optional: Pre-fill the username in login form
            document.getElementById('authUsername').value = username;
            
        } else {
            showMessage(data.error, 'error');
        }
    } catch (error) {
        showMessage('Registration failed', 'error');
    }
}

async function logout() {
    try {
        await fetch('/logout', { method: 'POST' });
        currentUser = null;
        updateAuthUI();
        // Clear login/register fields
        const loginFields = ['authUsername', 'authPassword'];
        const regFields = ['regUsername', 'regEmail', 'regPassword'];
        loginFields.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
        regFields.forEach(id => { const el = document.getElementById(id); if (el) el.value = ''; });
        showMessage('Logged out successfully', 'success');
        // Refresh the page after a short delay
        setTimeout(() => { window.location.reload(); }, 800);
    } catch (error) {
        showMessage('Logout failed', 'error');
    }
}

function updateAuthUI() {
    const authForms = document.getElementById('authForms');
    const userInfo = document.getElementById('userInfo');
    const loggedInActions = document.getElementById('loggedInActions');
    const registerForm = document.getElementById('registerForm');

    if (currentUser) {
        // Hide all forms
        authForms.style.display = 'none';
        registerForm.style.display = 'none';
        
        // Show user info and logout
        userInfo.style.display = 'block';
        loggedInActions.style.display = 'block';
        
        // Set username
        document.getElementById('username').textContent = currentUser;
        
        // Clear input fields
        document.getElementById('authUsername').value = '';
        document.getElementById('authPassword').value = '';
        document.getElementById('regUsername').value = '';
        document.getElementById('regEmail').value = '';
        document.getElementById('regPassword').value = '';
        
    } else {
        // Show login form
        authForms.style.display = 'flex';
        userInfo.style.display = 'none';
        loggedInActions.style.display = 'none';
        registerForm.style.display = 'none';
    }
}
// Tab switching
function switchTab(tabName) {
    // Remove active class from all tabs and contents
    document.querySelectorAll('.tab').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));

    // Add active class to selected tab and content
    event.target.classList.add('active');
    document.getElementById(tabName + 'Tab').classList.add('active');

    // Load data for specific tabs
    if (tabName === 'library' && currentUser) {
        loadMyStories();
    } else if (tabName === 'stats' && currentUser) {
        loadStats();
    }
}

// Story generation
async function generateStory() {
    const prompt = document.getElementById('storyPrompt').value.trim();
    if (!prompt) {
        showMessage('Please enter a story prompt', 'error');
        return;
    }

    const generateBtn = document.getElementById('generateBtn');
    const loading = document.getElementById('loading');
    const result = document.getElementById('storyResult');

    generateBtn.disabled = true;
    loading.style.display = 'block';
    result.style.display = 'none';

    try {
        const response = await fetch('/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: prompt,
                title: document.getElementById('storyTitle').value,
                genre: document.getElementById('genre').value,
                max_length: parseInt(document.getElementById('maxLength').value),
                temperature: parseFloat(document.getElementById('temperature').value),
                top_p: parseFloat(document.getElementById('topP').value),
                is_public: document.getElementById('makePublic').checked
            })
        });

        const data = await response.json();

        if (response.ok) {
            generatedStory = data.story;
            currentStoryId = data.story_id;
            document.getElementById('generatedStory').textContent = data.story;
            result.style.display = 'block';
            showMessage(`Story generated! (${data.word_count} words)`, 'success');
        } else {
            showMessage(data.error, 'error');
        }
    } catch (error) {
        showMessage('Failed to generate story', 'error');
    } finally {
        generateBtn.disabled = false;
        loading.style.display = 'none';
    }
}

// Story enhancement
async function enhanceStory() {
    const story = document.getElementById('storyToEnhance').value.trim();
    if (!story) {
        showMessage('Please enter a story to enhance', 'error');
        return;
    }

    const enhanceBtn = document.getElementById('enhanceBtn');
    const loading = document.getElementById('enhanceLoading');
    const result = document.getElementById('enhanceResult');

    enhanceBtn.disabled = true;
    loading.style.display = 'block';
    result.style.display = 'none';

    try {
        const response = await fetch('/enhance', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                story: story,
                type: document.getElementById('enhancementType').value
            })
        });

        const data = await response.json();

        if (response.ok) {
            document.getElementById('enhancedStory').textContent = data.enhanced_story;
            result.style.display = 'block';
            showMessage(`Story enhanced! (${data.word_count} words)`, 'success');
        } else {
            showMessage(data.error, 'error');
        }
    } catch (error) {
        showMessage('Failed to enhance story', 'error');
    } finally {
        enhanceBtn.disabled = false;
        loading.style.display = 'none';
    }
}

// Multiple endings
async function generateMultipleEndings() {
    const story = document.getElementById('storyForEndings').value.trim();
    if (!story) {
        showMessage('Please enter a story beginning', 'error');
        return;
    }

    const endingsBtn = document.getElementById('endingsBtn');
    const loading = document.getElementById('endingsLoading');
    const result = document.getElementById('endingsResult');

    endingsBtn.disabled = true;
    loading.style.display = 'block';
    result.style.display = 'none';

    try {
        const response = await fetch('/multiple-endings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                story: story,
                num_endings: parseInt(document.getElementById('numEndings').value)
            })
        });

        const data = await response.json();

        if (response.ok) {
            displayEndings(data.endings);
            result.style.display = 'block';
            showMessage(`Generated ${data.num_endings} different endings!`, 'success');
        } else {
            showMessage(data.error, 'error');
        }
    } catch (error) {
        showMessage('Failed to generate endings', 'error');
    } finally {
        endingsBtn.disabled = false;
        loading.style.display = 'none';
    }
}

function displayEndings(endings) {
    const container = document.getElementById('endingsContainer');
    container.innerHTML = ''; // Clear container first
    
    endings.forEach((ending, index) => {
        const endingCard = document.createElement('div');
        endingCard.className = 'ending-card';
        
        const title = document.createElement('h4');
        title.textContent = `Ending ${index + 1}`;
        
        const content = document.createElement('div');
        content.style.whiteSpace = 'pre-wrap';
        content.style.lineHeight = '1.6';
        content.textContent = ending;
        
        const copyBtn = document.createElement('button');
        copyBtn.className = 'btn btn-secondary btn-small';
        copyBtn.textContent = 'Copy';
        copyBtn.onclick = () => copyText(ending);
        
        endingCard.appendChild(title);
        endingCard.appendChild(content);
        endingCard.appendChild(copyBtn);
        
        container.appendChild(endingCard);
    });
}

// Random prompt
async function getRandomPrompt() {
    try {
        const response = await fetch('/random-prompt');
        const data = await response.json();
        document.getElementById('storyPrompt').value = data.prompt;
    } catch (error) {
        showMessage('Failed to get random prompt', 'error');
    }
}

// Load user stories
async function loadMyStories() {
    if (!currentUser) return;

    try {
        const response = await fetch('/my-stories');
        const data = await response.json();

        if (response.ok) {
            displayMyStories(data.stories);
        } else {
            showMessage(data.error, 'error');
        }
    } catch (error) {
        showMessage('Failed to load stories', 'error');
    }
}

function displayMyStories(stories) {
    const container = document.getElementById('myStoriesContainer');
    
    if (stories.length === 0) {
        container.innerHTML = '<p>No stories yet. Create your first story!</p>';
        return;
    }

    container.innerHTML = stories.map(story => 
        `<div class="story-card">
            <div class="story-meta">
                <div>
                    <strong>${story.title}</strong>
                    ${story.genre ? `<span class="genre-tag">${story.genre}</span>` : ''}
                </div>
                <div class="word-count">${story.word_count} words</div>
            </div>
            <div style="margin: 10px 0; color: #666; font-size: 14px;">
                ${story.prompt.substring(0, 100)}${story.prompt.length > 100 ? '...' : ''}
            </div>
            <div style="margin: 10px 0; font-size: 14px;">
                Created: ${new Date(story.created_at).toLocaleDateString()}
            </div>
            <div class="story-actions">
                
                <button class="btn btn-secondary btn-small" onclick="exportStoryPDF('${story.id}')">PDF</button>
            </div>
        </div>`
    ).join('');
}

// Load public stories
async function loadPublicStories() {
    try {
        const response = await fetch('/public-stories');
        const data = await response.json();

        if (response.ok) {
            displayPublicStories(data.stories);
        } else {
            showMessage(data.error, 'error');
        }
    } catch (error) {
        showMessage('Failed to load public stories', 'error');
    }
}

function displayPublicStories(stories) {
    const container = document.getElementById('publicStories');
    
    if (stories.length === 0) {
        container.innerHTML = '<p>No public stories yet.</p>';
        return;
    }

    container.innerHTML = stories.slice(0, 5).map(story => 
        `<div class="story-card" style="margin-bottom: 10px; padding: 10px;">
            <div style="font-size: 14px; font-weight: bold;">${story.title}</div>
            <div style="font-size: 12px; color: #666;">by ${story.username}</div>
            ${story.genre ? `<span class="genre-tag" style="font-size: 10px;">${story.genre}</span>` : ''}
        </div>`
    ).join('');
}

// Load statistics
async function loadStats() {
    if (!currentUser) return;

    try {
        const response = await fetch('/story-stats');
        const data = await response.json();

        if (response.ok) {
            displayStats(data);
        } else {
            showMessage(data.error, 'error');
        }
    } catch (error) {
        showMessage('Failed to load statistics', 'error');
    }
}

function displayStats(data) {
    const container = document.getElementById('statsContainer');
    const total = data.total_stats;

    if (!total || total.total_stories === 0) {
        container.innerHTML = '<p>No statistics available yet. Start writing!</p>';
        return;
    }

    const statsHTML = `
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">${total.total_stories || 0}</div>
                <div>Total Stories</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${total.total_words || 0}</div>
                <div>Total Words</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${Math.round(total.avg_words || 0)}</div>
                <div>Avg Words/Story</div>
            </div>
        </div>
        
        <h4>Genre Breakdown</h4>
        <div style="margin-top: 15px;">
            ${data.genre_stats.map(stat => 
                `<div style="display: flex; justify-content: space-between; margin: 5px 0; padding: 8px;  border-radius: 5px;">
                    <span>${stat.genre || 'No Genre'}</span>
                    <span>${stat.genre_count} stories</span>
                </div>`
            ).join('')}
        </div>
    `;

    container.innerHTML = statsHTML;
}

// Utility functions
function toggleAdvanced() {
    const settings = document.getElementById('advancedSettings');
    settings.style.display = document.getElementById('showAdvanced').checked ? 'block' : 'none';
}

function updateRangeValue(id) {
    const input = document.getElementById(id);
    const valueDisplay = document.getElementById(id + 'Value');
    let value = input.value;
    
    if (id === 'maxLength') {
        value += ' words';
    }
    
    valueDisplay.textContent = value;
}

function enhanceCurrentStory() {
    if (generatedStory) {
        document.getElementById('storyToEnhance').value = generatedStory;
        switchTab('enhance');
        document.querySelector('.tab[onclick="switchTab(\'enhance\')"]').click();
    } else {
        showMessage('No story to enhance', 'error');
    }
}

function generateEndingsForCurrent() {
    if (generatedStory) {
        document.getElementById('storyForEndings').value = generatedStory;
        switchTab('endings');
        document.querySelector('.tab[onclick="switchTab(\'endings\')"]').click();
    } else {
        showMessage('No story for endings', 'error');
    }
}

function copyToClipboard() {
    if (generatedStory) {
        navigator.clipboard.writeText(generatedStory);
        showMessage('Story copied to clipboard!', 'success');
    }
}

function copyEnhanced() {
    const enhanced = document.getElementById('enhancedStory').textContent;
    navigator.clipboard.writeText(enhanced);
    showMessage('Enhanced story copied!', 'success');
}

function copyText(text) {
    navigator.clipboard.writeText(text);
    showMessage('Text copied to clipboard!', 'success');
}

function useEnhanced() {
    const enhanced = document.getElementById('enhancedStory').textContent;
    generatedStory = enhanced;
    document.getElementById('generatedStory').textContent = enhanced;
    switchTab('generate');
    document.querySelector('.tab[onclick="switchTab(\'generate\')"]').click();
    showMessage('Using enhanced version', 'success');
}

async function exportStoryPDF(storyId) {
    try {
        window.open(`/export-pdf/${storyId}`, '_blank');
    } catch (error) {
        showMessage('Failed to export PDF', 'error');
    }
}

function exportPDF() {
    if (currentStoryId) {
        exportStoryPDF(currentStoryId);
    } else {
        showMessage('Please save the story first', 'error');
    }
}

function showMessage(message, type) {
    // Remove existing messages
    document.querySelectorAll('.error-message, .success-message, .warning-message, .info-message').forEach(el => el.remove());
    
    const messageDiv = document.createElement('div');
    messageDiv.className = type === 'error' ? 'error-message' : 
                         type === 'success' ? 'success-message' :
                         type === 'warning' ? 'warning-message' : 'info-message';
    messageDiv.textContent = message;
    
    const parent = document.querySelector('.story-generator');
    parent.insertBefore(messageDiv, document.querySelector('.tabs'));
    
    // Auto-remove with fade animation
    setTimeout(() => {
        messageDiv.classList.add('fade-out');
        setTimeout(() => messageDiv.remove(), 300);
    }, 5000);
}

// Input validation
function markInputError(inputId) {
    const input = document.getElementById(inputId);
    if (input) {
        input.classList.add('input-error');
        
        // Remove error styling after user starts typing
        input.addEventListener('input', () => {
            input.classList.remove('input-error');
        }, { once: true });
    }
}

// Initialize
document.addEventListener('DOMContentLoaded', function() {
    updateRangeValue('maxLength');
    updateRangeValue('temperature');
    updateRangeValue('topP');
    loadPublicStories();
});