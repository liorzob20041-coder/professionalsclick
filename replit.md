# Overview

ProfessionalsClick (בעלי מקצוע בקליק) is a professional marketplace web application that connects customers with local tradespeople and service providers in Israel. The platform allows users to search for professionals by profession and area, view detailed profiles with reviews, and contact providers directly. The application serves both customers looking for services and professionals wanting to list their services.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Framework**: Flask with Jinja2 templating
- **Multi-language Support**: Hebrew (primary), English, and Russian with translation files stored in JSON format
- **Responsive Design**: CSS-based responsive layouts with mobile-first approach
- **Static Assets**: Organized CSS, images, and JavaScript files with versioning support
- **Component Structure**: Modular template system with reusable components (navbar, base template, etc.)

## Backend Architecture
- **Framework**: Flask (Python) web application
- **Data Storage**: JSON-based file system for worker profiles, reviews, and translations
- **Session Management**: Flask sessions with CSRF protection using Flask-WTF
- **File Upload**: Werkzeug-based secure file handling for professional photos/videos
- **Email Service**: SMTP integration for contact forms and notifications

## Core Data Models
- **Workers/Professionals**: Stored in approved.json and pending.json with fields for company info, skills, location, experience, and media
- **Reviews**: Stored in worker_reviews.json with multi-language translations
- **Translations**: Organized by language and page in translations/ directory structure

## AI Integration
- **AI Writer Service**: Custom AI content generation using Ollama for professional bio and service descriptions
- **Translation Service**: Google Translator integration for automatic content translation
- **Deterministic Variants**: Hashlib-based consistent AI content generation

## Search and Filtering
- **Geographic Search**: City-based filtering with radius support
- **Professional Categories**: Field-based categorization (electricians, plumbers, renovators, etc.)
- **Advanced Filtering**: Experience, rating, availability, and media presence filters

## External Dependencies

- **Google Sheets Integration**: Webhook synchronization for data management and analytics
- **Google Translator**: Automatic translation service for multi-language content
- **Ollama AI**: Local AI service for content generation (configurable endpoint)
- **Email Services**: SMTP for contact forms and notifications
- **WhatsApp Integration**: Direct messaging links for customer communication
- **Image Processing**: PIL (Pillow) for image handling and optimization

## Security Features
- **CSRF Protection**: Flask-WTF CSRF tokens on all forms
- **Content Security Policy**: Implemented CSP headers
- **Input Validation**: Secure filename handling and form validation
- **Rate Limiting**: Thread-safe JSON file operations with locks
- **Environment Variables**: Sensitive configuration stored in .env files

## Analytics and Monitoring
- **Custom Analytics**: Built-in tracking for profile views, calls, and WhatsApp interactions
- **Admin Dashboard**: Protected admin interface for managing professional applications
- **Monthly/All-time Reports**: Comprehensive analytics dashboard with filtering capabilities