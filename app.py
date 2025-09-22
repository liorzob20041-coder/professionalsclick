from flask import Flask, render_template, request, url_for, redirect
import os
import json

app = Flask(__name__)
app.secret_key = os.environ.get('SESSION_SECRET', 'dev-secret-key')

# Configuration
app.config['LANGUAGES'] = {
    'he': 'עברית',
    'en': 'English', 
    'ru': 'Русский'
}

# Sample data structure for professionals (placeholder)
SAMPLE_PROFESSIONALS = [
    {
        'id': 1,
        'name': 'יוסי כהן',
        'company': 'חשמל יוסי',
        'category': 'electrician',
        'city': 'תל אביב',
        'experience_years': 15,
        'rating': 4.8,
        'reviews_count': 127,
        'phone': '050-1234567',
        'services': ['התקנת חשמל', 'תיקון תקלות', 'בדיקות חשמל'],
        'description': 'חשמלאי מוסמך עם ניסיון של 15 שנה בכל סוגי העבודות החשמליות',
        'last_review': 'שירות מהיר ומקצועי, ממליץ בחום!'
    },
    {
        'id': 2,
        'name': 'דוד לוי',
        'company': 'אינסטלציה דוד',
        'category': 'plumber',
        'city': 'חיפה',
        'experience_years': 12,
        'rating': 4.6,
        'reviews_count': 89,
        'phone': '050-9876543',
        'services': ['תיקון צנרת', 'התקנת מקלחונים', 'פתיחת סתימות'],
        'description': 'שרברב מנוסה המתמחה בתיקונים מורכבים ושדרוגי אמבטיות',
        'last_review': 'פתר את הבעיה במהירות ובמחיר הוגן'
    }
]

CATEGORIES = [
    {'id': 'electrician', 'name': 'חשמלאי', 'icon': 'electric'},
    {'id': 'plumber', 'name': 'שרברב', 'icon': 'water'},
    {'id': 'renovator', 'name': 'שיפוצים', 'icon': 'hammer'},
    {'id': 'painter', 'name': 'צייר', 'icon': 'paint'},
    {'id': 'cleaner', 'name': 'ניקיון', 'icon': 'clean'},
    {'id': 'gardener', 'name': 'גינון', 'icon': 'garden'}
]

@app.route('/')
@app.route('/<lang>')
def home(lang='he'):
    if lang not in app.config['LANGUAGES']:
        lang = 'he'
    return render_template('home.html', lang=lang, categories=CATEGORIES)

@app.route('/<lang>/professionals')
@app.route('/<lang>/professionals/<category>')
def professionals_listing(lang='he', category=None):
    if lang not in app.config['LANGUAGES']:
        lang = 'he'
    
    professionals = SAMPLE_PROFESSIONALS
    if category:
        professionals = [p for p in professionals if p['category'] == category]
    
    return render_template('professionals_listing.html', 
                         lang=lang, 
                         professionals=professionals, 
                         categories=CATEGORIES,
                         current_category=category)

@app.route('/<lang>/professional/<int:professional_id>')
def professional_profile(lang='he', professional_id=None):
    if lang not in app.config['LANGUAGES']:
        lang = 'he'
    
    professional = next((p for p in SAMPLE_PROFESSIONALS if p['id'] == professional_id), None)
    if not professional:
        return redirect(url_for('professionals_listing', lang=lang))
    
    return render_template('professional_profile.html', 
                         lang=lang, 
                         professional=professional)

@app.route('/<lang>/request', methods=['GET', 'POST'])
def request_quote(lang='he'):
    if lang not in app.config['LANGUAGES']:
        lang = 'he'
    
    if request.method == 'POST':
        # Handle form submission
        form_data = {
            'name': request.form.get('name'),
            'phone': request.form.get('phone'),
            'email': request.form.get('email'),
            'category': request.form.get('category'),
            'city': request.form.get('city'),
            'description': request.form.get('description')
        }
        # In real app, save to database and send to professionals
        return render_template('request_success.html', lang=lang)
    
    return render_template('request_form.html', lang=lang, categories=CATEGORIES)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)