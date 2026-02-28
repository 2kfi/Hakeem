from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from markdown_it import MarkdownIt

app = Flask(__name__)
md = MarkdownIt()

# This key encrypts your session cookies so users can't fake them
app.secret_key = 'a_very_secret_random_string'

# Mock Database (Replace with a real database later)
USER_DB = {
    "user123": "password456"
}

# --- ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
        return redirect(url_for('chat'))

    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        password = data.get('password')

        if username in USER_DB and USER_DB[username] == password:
            session['user'] = username  # This "logs them in"
            return jsonify({"success": True}), 200
        else:
            return jsonify({"success": False, "message": "Invalid Credentials"}), 401
    
    # If it's a GET request, just show the login page
    return render_template('login.html')

@app.route('/chat')
def chat():
    # SECURITY: Check if the user is actually logged in
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('chat.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/about')
def about():
    with open('ABOUT.md', 'r') as f:
        content = f.read()
    html_content = md.render(content)
    return render_template('about.html', content=html_content)

@app.route('/team')
def team():
    return render_template('team.html')

@app.route('/sales')
def sales():
    return render_template('sales.html')

@app.route('/demo')
def demo():
    return render_template('demo.html')

if __name__ == '__main__':
    # Run on port 8080
    app.run(port=4245, debug=True)